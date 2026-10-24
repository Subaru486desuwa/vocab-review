"""目标词表、组卷与作答事务，接口契约见 docs/api.md。"""

import json
import random

from app.repositories import db
from app.repositories import practice as repo
from app.repositories import progress as progress_repo
from app.repositories import wordbooks as wordbook_repo
from app.services import grading, review_rules
from app.services.content_import import EXAM_TYPES, SKILL_TYPES

DEFAULT_COUNT = 10
MAX_COUNT = 20
# new_senses：只出任何题型都未作答的词义（今日新词义）。
FOCUSES = ("new_senses",)
PAGE_SIZE = 20


class InvalidRequest(Exception):
    def __init__(self, fields):
        super().__init__("参数校验失败")
        self.fields = fields


class NoTarget(Exception):
    pass


class NoQuestions(Exception):
    pass


class NotFound(Exception):
    pass


class AlreadySubmitted(Exception):
    pass


class SessionClosed(Exception):
    pass


# ---- 目标词表 ----


def list_wordbooks(conn, user_id, exam_type=None, page=1):
    if exam_type is not None and exam_type not in EXAM_TYPES:
        raise InvalidRequest({"exam_type": "exam_type 只能为 " + "/".join(EXAM_TYPES)})
    if not isinstance(page, int) or page < 1:
        raise InvalidRequest({"page": "page 必须是正整数"})
    with db.transaction(conn):
        rows = wordbook_repo.list_active(conn, user_id, exam_type, PAGE_SIZE, (page - 1) * PAGE_SIZE)
        total = wordbook_repo.count_active(conn, exam_type)
    items = [{**row, "selected": bool(row["selected"])} for row in rows]
    return {"items": items, "page": page, "page_size": PAGE_SIZE, "total": total}


def set_targets(conn, user_id, wordbook_ids, now):
    """一次替换全部目标；任一 id 无效则不做任何修改。"""
    if not isinstance(wordbook_ids, list) or not all(_is_id(i) for i in wordbook_ids):
        raise InvalidRequest({"wordbook_ids": "wordbook_ids 必须是词表 id 列表"})
    ids = list(dict.fromkeys(wordbook_ids))
    with db.transaction(conn):
        wordbook_repo.lock_user(conn, user_id)
        invalid = [i for i in ids if i not in wordbook_repo.active_ids(conn, ids)]
        if invalid:
            raise InvalidRequest({"wordbook_ids": invalid})
        wordbook_repo.replace_selection(conn, user_id, ids, now)
        return wordbook_repo.selected(conn, user_id)


def _is_id(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


# ---- 组卷 ----


def create_session(conn, user_id, skill_type, count, wordbook_ids, now, rng=None, focus=None):
    """按 到期复习 > 未到期错题 > 未测试 > 其他 的优先级组卷，同级随机，每个词义最多一题。

    focus="new_senses" 时只从任何题型都未作答的词义中随机取题。
    """
    rng = rng or random.SystemRandom()
    fields = {}
    if skill_type not in SKILL_TYPES:
        fields["skill_type"] = "skill_type 只能为 " + "/".join(SKILL_TYPES)
    if not _is_id(count) or count > MAX_COUNT:
        fields["count"] = f"count 必须是 1—{MAX_COUNT} 的整数"
    if wordbook_ids is not None and (not isinstance(wordbook_ids, list) or not all(_is_id(i) for i in wordbook_ids)):
        fields["wordbook_ids"] = "wordbook_ids 必须是词表 id 列表"
    if focus is not None and focus not in FOCUSES:
        fields["focus"] = "focus 只能为 " + "/".join(FOCUSES)
    if fields:
        raise InvalidRequest(fields)
    with db.transaction(conn):
        selected = wordbook_repo.selected(conn, user_id)
        if not selected:
            raise NoTarget
        if wordbook_ids is not None:
            chosen_ids = set(wordbook_ids)
            not_selected = sorted(chosen_ids - {b["id"] for b in selected})
            if not_selected or not chosen_ids:
                raise InvalidRequest({"wordbook_ids": not_selected or "至少选择一个目标词表"})
            selected = [b for b in selected if b["id"] in chosen_ids]
        senses = repo.candidate_senses(conn, [b["id"] for b in selected], skill_type)
        if focus == "new_senses":
            attempted = progress_repo.first_attempts(conn, user_id)
            senses = [s for s in senses if s not in attempted]
        if not senses:
            raise NoQuestions
        if focus == "new_senses":
            rng.shuffle(senses)
            chosen = senses[:count]
        else:
            states = repo.learning_states(conn, user_id, skill_type, senses)
            chosen = _prioritize(senses, states, now, count, rng)
        by_sense = {}
        for question in repo.published_questions(conn, chosen, skill_type):
            by_sense.setdefault(question["sense_id"], []).append(question["id"])
        snapshot = {
            "wordbooks": [{k: b[k] for k in ("id", "code", "version", "exam_type", "name")} for b in selected],
            "skill_type": skill_type,
            "count": count,
            "focus": focus,
            "review_rule_version": review_rules.VERSION,
        }
        session_id = repo.insert_session(conn, user_id, json.dumps(snapshot, ensure_ascii=False), now)
        repo.insert_items(conn, session_id, [rng.choice(by_sense[s]) for s in chosen], now)
    return get_session(conn, user_id, session_id)


def _prioritize(senses, states, now, count, rng):
    due, wrong, untested, rest = [], [], [], []
    for sense_id in senses:
        state = states.get(sense_id)
        if state is None or state["seen_count"] == 0:
            untested.append(sense_id)
        elif state["next_review_at"] is not None and state["next_review_at"] <= now:
            due.append(sense_id)
        elif state["correct_streak"] == 0:
            wrong.append(sense_id)
        else:
            rest.append(sense_id)
    for bucket in (due, wrong, untested, rest):
        rng.shuffle(bucket)
    return (due + wrong + untested + rest)[:count]


# ---- 查看 ----


def get_session(conn, user_id, session_id):
    with db.transaction(conn):
        session = repo.find_session(conn, session_id, user_id)
        if session is None:
            raise NotFound
        rows = repo.session_items(conn, session_id)
    snapshot = json.loads(session["target_snapshot_json"])
    items = [_item_view(row) for row in rows]
    return {
        "id": session["id"],
        "status": session["status"],
        "skill_type": snapshot["skill_type"],
        "focus": snapshot.get("focus"),
        "wordbooks": snapshot["wordbooks"],
        "started_at": _iso(session["started_at"]),
        "finished_at": _iso(session["finished_at"]),
        "total": len(items),
        "answered": sum(1 for item in items if item["result"] is not None),
        "items": items,
    }


def _question(row):
    return {
        "skill_type": row["skill_type"],
        "options": json.loads(row["options_json"]) if row["options_json"] else None,
        "answers": json.loads(row["answers_json"]),
        "grading_policy": json.loads(row["grading_policy_json"]),
    }


def _item_view(row):
    # 未作答时只给题干与选项，不返回答案或判分规则。
    question = _question(row)
    return {
        "id": row["id"],
        "position": row["position"],
        "skill_type": row["skill_type"],
        "prompt": row["prompt"],
        "options": question["options"],
        "result": _result(row, row, question) if row["attempt_id"] else None,
    }


def _result(item, attempt, question):
    return {
        "item_id": item["id"],
        "is_correct": bool(attempt["is_correct"]),
        "error_type": attempt["error_type"],
        "normalized_answer": attempt["normalized_answer"],
        "correct_answer": grading.correct_answer(question),
        "lemma": item["lemma"],
        "definition_zh": item["definition_zh"],
        "submitted_at": _iso(attempt["attempt_submitted_at"]),
    }


def _iso(value):
    return None if value is None else value.isoformat() + "Z"


# ---- 作答 ----


def submit_answer(conn, user_id, item_id, raw_answer, now):
    """单一写事务：校验归属、加锁、幂等重放或判分，写作答并更新学习状态。

    now 是取服务端时间的函数，在拿到全部行锁之后调用。
    """
    with db.transaction(conn):
        owner = repo.find_item_session(conn, item_id, user_id)
        if owner is None:
            raise NotFound
        session = repo.lock_session(conn, owner["session_id"])
        repo.lock_item(conn, item_id)
        item = repo.item_with_question(conn, item_id)
        question = _question(item)
        normalized = grading.normalize(question, raw_answer)
        attempt = repo.lock_attempt(conn, item_id)
        if attempt is not None:
            if attempt["normalized_answer"] != normalized:
                raise AlreadySubmitted
            return {**_result(item, attempt, question), "replayed": True, "session_status": session["status"]}
        if session["status"] != "active":
            raise SessionClosed
        is_correct, error_type = grading.grade(question, normalized)
        repo.ensure_learning_state(conn, user_id, item["sense_id"], item["skill_type"])
        state = repo.lock_learning_state(conn, user_id, item["sense_id"], item["skill_type"])
        submitted_at = now()
        repo.insert_attempt(
            conn,
            session_item_id=item_id,
            raw_answer_json=json.dumps({"answer": raw_answer}, ensure_ascii=False),
            normalized_answer=normalized,
            is_correct=is_correct,
            error_type=error_type,
            review_rule_version=review_rules.VERSION,
            submitted_at=submitted_at,
        )
        repo.update_learning_state(conn, state["id"], review_rules.apply(state, is_correct, submitted_at))
        repo.mark_item_submitted(conn, item_id, submitted_at)
        status = session["status"]
        if repo.count_unsubmitted(conn, owner["session_id"]) == 0:
            repo.complete_session(conn, owner["session_id"], submitted_at)
            status = "completed"
    attempt = {
        "is_correct": is_correct,
        "error_type": error_type,
        "normalized_answer": normalized,
        "attempt_submitted_at": submitted_at,
    }
    return {**_result(item, attempt, question), "replayed": False, "session_status": status}
