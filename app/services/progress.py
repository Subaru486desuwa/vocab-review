"""复习清单与学习统计：只读取作答事实与学习状态投影，每个数字注明粒度与分母。"""

from datetime import timedelta

from app.repositories import db
from app.repositories import progress as repo
from app.repositories import wordbooks as wordbook_repo
from app.services import evidence
from app.services.content_import import SKILL_TYPES
from app.services.practice import InvalidRequest, NoTarget, _is_id, _iso

CONSISTENT_RUN = 3
CONSISTENT_SPAN = timedelta(hours=24)
RECENT_WINDOW = timedelta(days=7)
GRANULARITY = {
    "words": "词条：目标词表并集，共有词条只计一次；含有至少一次作答的词条计为已练习",
    "items": "词义 × 题型：只计有已发布题目的组合；无有效作答为未测试",
    "attempts": "作答：每个题目实例的一次有效提交；重放不重复计数",
}


def _scope(conn, user_id, wordbook_id, skill_type):
    fields = {}
    if skill_type is not None and skill_type not in SKILL_TYPES:
        fields["skill_type"] = "skill_type 只能为 " + "/".join(SKILL_TYPES)
    if wordbook_id is not None and not _is_id(wordbook_id):
        fields["wordbook_id"] = "wordbook_id 必须是正整数"
    if fields:
        raise InvalidRequest(fields)
    books = wordbook_repo.selected(conn, user_id)
    if not books:
        raise NoTarget
    if wordbook_id is not None:
        books = [b for b in books if b["id"] == wordbook_id]
        if not books:
            raise InvalidRequest({"wordbook_id": "必须是当前已选的目标词表"})
    return books


def _scope_view(books, skill_type):
    return {
        "wordbooks": [{k: b[k] for k in ("id", "code", "version", "exam_type", "name")} for b in books],
        "skill_type": skill_type,
    }


def review_list(conn, user_id, now, wordbook_id=None, skill_type=None):
    """到期复习与未到期错题（附剩余时间与记忆强度）；未作答过的词义不出现。

    到期项按记忆强度从低到高排列，与默认组卷的到期顺序一致。
    """
    with db.transaction(conn):
        books = _scope(conn, user_id, wordbook_id, skill_type)
        senses = {s["sense_id"]: s for s in repo.scope_senses(conn, [b["id"] for b in books])}
        states = repo.learning_states(conn, user_id, list(senses)) if senses else []
        attempts = repo.attempts_for(conn, user_id, list(senses)) if senses else []
    found = evidence.items(attempts, now)
    due, pending, upcoming = [], [], []
    for state in states:
        if (skill_type and state["skill_type"] != skill_type) or state["seen_count"] == 0:
            continue
        next_at = state["next_review_at"]
        if next_at is not None and next_at > now:
            upcoming.append(next_at)
        is_due = next_at is not None and next_at <= now
        if not is_due and state["correct_streak"] != 0:
            continue
        sense = senses[state["sense_id"]]
        item = found.get((state["sense_id"], state["skill_type"]))
        entry = {
            "sense_id": state["sense_id"],
            "lemma": sense["lemma"],
            "part_of_speech": sense["part_of_speech"],
            "definition_zh": sense["definition_zh"],
            "skill_type": state["skill_type"],
            "seen_count": state["seen_count"],
            "correct_count": state["correct_count"],
            "correct_streak": state["correct_streak"],
            "last_attempt_at": _iso(state["last_attempt_at"]),
            "next_review_at": _iso(next_at),
            "seconds_until_due": 0 if is_due else int((next_at - now).total_seconds()),
            "recall": item["recall"] if item else None,
            "strength": item["strength"] if item else None,
            "status": item["status"] if item else None,
            "_order": (item["recall"] if item and is_due else 0, next_at, state["sense_id"], state["skill_type"]),
        }
        (due if is_due else pending).append(entry)
    for bucket in (due, pending):
        bucket.sort(key=lambda e: e.pop("_order"))
    return {
        "scope": _scope_view(books, skill_type),
        "now": _iso(now),
        "due": due,
        "wrong_pending": pending,
        "next_due_at": _iso(min(upcoming)) if upcoming else None,
    }


def _attempt_summary(attempts):
    correct = sum(1 for a in attempts if a["is_correct"])
    return {
        "count": len(attempts),
        "correct": correct,
        "accuracy": round(correct / len(attempts), 4) if attempts else None,
    }


def _recently_consistent(history):
    """最近三次均正确，且第一次与第三次相隔不少于 24 小时；以作答事实判断，不只看 correct_streak。"""
    last = history[-CONSISTENT_RUN:]
    return (
        len(last) == CONSISTENT_RUN
        and all(a["is_correct"] for a in last)
        and last[-1]["submitted_at"] - last[0]["submitted_at"] >= CONSISTENT_SPAN
    )


def _item_summary(pairs, states, histories, now):
    tested = {key: s for key, s in states.items() if key in pairs and s["seen_count"] > 0}
    due = [s for s in tested.values() if s["next_review_at"] is not None and s["next_review_at"] <= now]
    pending = [s for s in tested.values() if s not in due and s["correct_streak"] == 0]
    return {
        "total": len(pairs),
        "tested": len(tested),
        "untested": len(pairs) - len(tested),
        "due": len(due),
        "wrong_pending": len(pending),
        "recently_consistent": sum(1 for key in pairs if _recently_consistent(histories.get(key, []))),
    }


def stats(conn, user_id, now, wordbook_id=None, skill_type=None):
    with db.transaction(conn):
        books = _scope(conn, user_id, wordbook_id, skill_type)
        book_ids = [b["id"] for b in books]
        senses = repo.scope_senses(conn, book_ids)
        sense_ids = [s["sense_id"] for s in senses]
        memberships = repo.wordbook_words(conn, book_ids)
        pairs = repo.published_pairs(conn, sense_ids) if sense_ids else set()
        state_rows = repo.learning_states(conn, user_id, sense_ids) if sense_ids else []
        attempts = repo.attempts_for(conn, user_id, sense_ids) if sense_ids else []
    skills = [skill_type] if skill_type else list(SKILL_TYPES)
    word_of = {s["sense_id"]: s["word_id"] for s in senses}
    states = {(s["sense_id"], s["skill_type"]): s for s in state_rows}
    attempts = [a for a in attempts if a["skill_type"] in skills]
    histories = {}
    for a in attempts:
        histories.setdefault((a["sense_id"], a["skill_type"]), []).append(a)
    recent_since = now - RECENT_WINDOW

    def summarize(skill_subset):
        subset_pairs = {p for p in pairs if p[1] in skill_subset}
        subset_attempts = [a for a in attempts if a["skill_type"] in skill_subset]
        return {
            "items": _item_summary(subset_pairs, states, histories, now),
            "attempts": {
                "all_time": _attempt_summary(subset_attempts),
                "last_7_days": _attempt_summary([a for a in subset_attempts if a["submitted_at"] > recent_since]),
            },
        }

    overall = summarize(skills)
    practiced_words = {word_of[a["sense_id"]] for a in attempts}
    book_words = {}
    for m in memberships:
        book_words.setdefault(m["wordbook_id"], set()).add(m["word_id"])
    all_words = set().union(*book_words.values()) if book_words else set()
    return {
        "scope": _scope_view(books, skill_type),
        "generated_at": _iso(now),
        "granularity": GRANULARITY,
        "words": {"granularity": GRANULARITY["words"], "total": len(all_words), "practiced": len(practiced_words)},
        "items": {"granularity": GRANULARITY["items"], **overall["items"]},
        "attempts": {"granularity": GRANULARITY["attempts"], **overall["attempts"]},
        "by_skill": {skill: summarize([skill]) for skill in skills},
        "by_wordbook": [
            {
                "id": b["id"],
                "code": b["code"],
                "name": b["name"],
                "words_total": len(book_words.get(b["id"], ())),
                "words_practiced": len(book_words.get(b["id"], set()) & practiced_words),
            }
            for b in books
        ],
    }
