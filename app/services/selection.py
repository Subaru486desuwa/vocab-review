"""选题决策（selection_v1）：决定一组练习出哪些词义，并给每题留下选题理由。

纯函数，不读写数据库；输入为候选词义、学习状态与当前证据（evidence_v1）。
复习时间仍由 review_rules 决定；记忆强度只用于同级内排序与弱项专练，不改写学习状态。
"""

from app.services.evidence import fading_order, weak_order

VERSION = "selection_v1"
REASONS = ("due", "wrong_pending", "untested", "consolidate", "new_sense", "weak", "fading", "targeted")


def _reason(code, item=None):
    reason = {"code": code}
    if item is not None:
        reason.update(recall=item["recall"], recent_wrong=item["recent_wrong"], recent_count=len(item["recent"]))
    return reason


def _by_recall(sense_ids, evidence):
    return sorted(sense_ids, key=lambda s: (evidence[s]["recall"], s) if s in evidence else (1.0, s))


def default(senses, states, evidence, now, count, rng):
    """到期复习 > 未到期错题 > 未测试 > 巩固；到期、错题与巩固按记忆强度从低到高，未测试随机。

    states、evidence 均以 sense_id 为键，且只含本题型。
    """
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
    rng.shuffle(untested)
    plan = [(s, "due") for s in _by_recall(due, evidence)]
    plan += [(s, "wrong_pending") for s in _by_recall(wrong, evidence)]
    plan += [(s, "untested") for s in untested]
    plan += [(s, "consolidate") for s in _by_recall(rest, evidence)]
    return [(s, _reason(code, evidence.get(s))) for s, code in plan[:count]]


def weak(senses, evidence, count):
    """弱项专练：当前弱项在前（近期错误比例高、半衰期短），其后为记忆衰减项。"""
    pool = [evidence[s] for s in senses if s in evidence]
    weak_items = sorted((i for i in pool if i["status"] == "weak"), key=weak_order)
    fading = sorted((i for i in pool if i["status"] == "fading"), key=fading_order)
    return [(i["sense_id"], _reason(i["status"], i)) for i in (weak_items + fading)[:count]]


def targeted(senses, wanted, evidence, count):
    """按指定词义定向练习，保持请求顺序；不可练的词义（不在目标或无已发布题目）跳过。"""
    available = set(senses)
    chosen = [s for s in dict.fromkeys(wanted) if s in available][:count]
    return [(s, _reason("targeted", evidence.get(s))) for s in chosen]


def new_senses(senses, count, rng):
    pool = list(senses)
    rng.shuffle(pool)
    return [(s, _reason("new_sense")) for s in pool[:count]]
