"""学习诊断：从作答事实做规则统计，并用实验三、四的已有制品给出参考分析；只读，不改写作答与学习状态。

模型部分只作参考：实验三模型在 Duolingo 词条记录上训练，本系统按 词义 × 题型 计数，跨域适用性未经验证；
语义分组与“语义相近”使用固定阈值，未经标注评价。
"""

import json
import time
from collections import Counter, defaultdict

from app.repositories import db
from app.repositories import insights as repo
from app.repositories import progress as progress_repo
from app.services import grading
from app.services.content_import import SKILL_TYPES

TOP = 10
SPELLING_KINDS = ("missing_letter", "extra_letter", "wrong_letter", "transposition", "other", "unanswered")
GRANULARITY = (
    "范围为该用户全部作答，不按目标词表过滤。规则统计直接来自作答事实；遗忘风险与分组是实验三模型的参考估计，"
    "语义分组与相似度来自实验四编码器，均不改变组卷、复习安排和统计。"
)


def _question(row):
    return {
        "skill_type": row["skill_type"],
        "options": json.loads(row["options_json"]) if row["options_json"] else None,
        "answers": json.loads(row["answers_json"]),
        "grading_policy": json.loads(row["grading_policy_json"]),
    }


def edit_distance(a, b):
    """Damerau–Levenshtein（相邻换位算一次）的最优字符串对齐距离。"""
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[len(a)][len(b)]


def spelling_kind(answer, accepted):
    """把错误拼写与最接近的可接受答案比较，归为一类；accepted 与 answer 已按同一判分规则标准化。"""
    if not answer.strip():
        return "unanswered", None
    target = min(accepted, key=lambda a: (edit_distance(answer, a), a))
    if edit_distance(answer, target) != 1:
        return "other", target
    if len(answer) < len(target):
        return "missing_letter", target
    if len(answer) > len(target):
        return "extra_letter", target
    diff = [i for i, (x, y) in enumerate(zip(answer, target, strict=True)) if x != y]
    return ("wrong_letter" if len(diff) == 1 else "transposition"), target


def sense_summary(row):
    return {k: row[k] for k in ("sense_id", "lemma", "sense_key", "part_of_speech", "definition_zh")}


def _chosen_sense(question, chosen_text, by_zh, by_lemma):
    """误选选项对应的本系统词义：辨义题按中文释义，语境题按词条（多义词条无法确定时为 None）。"""
    if question["skill_type"] == "recognition":
        matches = by_zh.get(chosen_text, [])
    else:
        matches = by_lemma.get(chosen_text.casefold(), [])
    return matches[0] if len(matches) == 1 else None


def rules(rows, senses):
    """规则统计：错误类型、最常错的词义、误选的选项与拼写错法。rows 为 attempt_details 的结果。"""
    by_zh, by_lemma = defaultdict(list), defaultdict(list)
    for s in senses:
        by_zh[s["definition_zh"]].append(s)
        by_lemma[s["lemma_norm"].casefold()].append(s)
    per_sense = {}
    error_types = Counter()
    confusions = {}
    spelling = Counter()
    spelling_examples = []
    for row in rows:
        entry = per_sense.setdefault(row["sense_id"], {**sense_summary(row), "attempts": 0, "wrong": 0})
        entry["attempts"] += 1
        if row["is_correct"]:
            continue
        entry["wrong"] += 1
        error_types[row["error_type"]] += 1
        question = _question(row)
        answer = row["normalized_answer"]
        if row["skill_type"] == "spelling":
            accepted = sorted({grading.normalize(question, a) for a in question["answers"]["accepted"]})
            kind, target = spelling_kind(answer, accepted)
            spelling[kind] += 1
            if target is not None:
                spelling_examples.append({"lemma": row["lemma"], "answer": answer, "correct": target, "kind": kind})
        elif answer:
            options = {o["id"]: o["text"] for o in question["options"]}
            chosen = options[answer]
            key = (row["sense_id"], row["skill_type"], chosen)
            if key not in confusions:
                matched = _chosen_sense(question, chosen, by_zh, by_lemma)
                confusions[key] = {
                    "sense": sense_summary(row),
                    "skill_type": row["skill_type"],
                    "correct": options[question["answers"]["option_id"]],
                    "chosen": chosen,
                    "chosen_sense": sense_summary(matched) if matched else None,
                    "count": 0,
                }
            confusions[key]["count"] += 1
    most_wrong = sorted(
        (e for e in per_sense.values() if e["wrong"]),
        key=lambda e: (-e["wrong"], e["wrong"] - e["attempts"], e["sense_id"]),
    )
    return {
        "attempts": {"count": len(rows), "wrong": sum(error_types.values())},
        "error_types": dict(sorted(error_types.items())),
        "most_wrong": most_wrong[:TOP],
        "confusions": sorted(confusions.values(), key=lambda c: (-c["count"], c["sense"]["sense_id"], c["chosen"])),
        "spelling": {
            "counts": {kind: spelling[kind] for kind in SPELLING_KINDS},
            "examples": spelling_examples[-TOP:][::-1],
        },
    }


def load(conn, user_id):
    with db.transaction(conn):
        rows = repo.attempt_details(conn, user_id)
        senses = repo.all_senses(conn) if rows else []
        states = [s for s in progress_repo.all_learning_states(conn, user_id) if s["seen_count"] > 0]
    return rows, senses, states


def ml_inputs(states, now):
    """每个已作答的 词义 × 题型：[sense_id, skill_type, delta_seconds, seen, correct]，按词义与题型排序。"""
    items = [
        [
            s["sense_id"],
            s["skill_type"],
            max((now - s["last_attempt_at"]).total_seconds(), 0.0),
            s["seen_count"],
            s["correct_count"],
        ]
        for s in states
    ]
    return sorted(items, key=lambda i: (i[0], SKILL_TYPES.index(i[1])))


def ml_analysis(loaded, items):
    """实验三模型批量预测 expected_recall，再做 KMeans 分组；返回 (结果, model_time_ms)。"""
    from ml.diagnosis import group_items
    from ml.features import build_recall_features

    started = time.perf_counter()
    features = build_recall_features(*zip(*[i[2:] for i in items], strict=True))
    predicted = [min(max(float(v), 0.0), 1.0) for v in loaded.estimator.predict(features)]
    groups = group_items(features, predicted)
    return {"expected_recall": predicted, "groups": groups}, (time.perf_counter() - started) * 1000


def ml_view(items, result, sense_rows):
    """遗忘风险前 TOP 项与分组摘要。sense_rows 为 sense_id → 词义信息。"""
    entries = [
        {
            **sense_summary(sense_rows[sense_id]),
            "skill_type": skill,
            "days_since": round(delta / 86400, 1),
            "seen": seen,
            "correct": correct,
            "expected_recall": round(value, 4),
        }
        for (sense_id, skill, delta, seen, correct), value in zip(items, result["expected_recall"], strict=True)
    ]
    risk = sorted(entries, key=lambda e: (e["expected_recall"], e["sense_id"], SKILL_TYPES.index(e["skill_type"])))
    groups = None
    if result["groups"] is not None:
        from ml.diagnosis import GROUP_NAMES

        groups = []
        for k, name in enumerate(GROUP_NAMES):
            members = [e for e, g in zip(entries, result["groups"], strict=True) if g == k]
            groups.append(
                {
                    "name": name,
                    "count": len(members),
                    "mean_expected_recall": round(sum(m["expected_recall"] for m in members) / len(members), 4),
                    "mean_accuracy": round(sum(m["correct"] for m in members) / sum(m["seen"] for m in members), 4),
                    "mean_days_since": round(sum(m["days_since"] for m in members) / len(members), 1),
                    "examples": sorted(members, key=lambda m: m["expected_recall"])[:5],
                }
            )
    return {"risk": risk[:TOP], "groups": groups, "items": len(entries)}


def dl_inputs(rule_result, rows, senses):
    """答错过的词义、可对应词义的误选对（正确词义, 误选词义）与各词义文本 “lemma: definition_en”。

    没有英文释义的词义跳过；误选对按 rule_result["confusions"] 的顺序，无法对应的记为 None。
    """
    texts = {s["sense_id"]: f"{s['lemma']}: {s['definition_en']}" for s in senses if s["definition_en"]}
    wrong_ids = sorted({r["sense_id"] for r in rows if not r["is_correct"] and r["sense_id"] in texts})
    pairs = []
    for c in rule_result["confusions"]:
        chosen = c["chosen_sense"]
        target = c["sense"]["sense_id"]
        ok = chosen is not None and target in texts and chosen["sense_id"] in texts
        pairs.append((target, chosen["sense_id"]) if ok else None)
    return wrong_ids, pairs, texts


def dl_analysis(model, wrong_ids, texts, pairs):
    """编码错题词义与误选词义，层次聚类并计算误选对的相似度；返回 (结果, model_time_ms)。"""
    from ml.diagnosis import cluster_senses
    from ml.example_index import encode

    started = time.perf_counter()
    ids = sorted(set(wrong_ids) | {i for pair in pairs if pair for i in pair})
    vectors = dict(zip(ids, encode(model, [texts[i] for i in ids]), strict=True)) if ids else {}
    labels = cluster_senses([vectors[i] for i in wrong_ids])
    similarity = [round(float(vectors[p[0]] @ vectors[p[1]]), 4) if p else None for p in pairs]
    groups = defaultdict(list)
    for sense_id, label in zip(wrong_ids, labels, strict=True):
        groups[label].append(sense_id)
    clusters = sorted((g for g in groups.values() if len(g) > 1), key=lambda g: (-len(g), g[0]))
    cohesion = []
    for group in clusters:
        sims = [float(vectors[a] @ vectors[b]) for i, a in enumerate(group) for b in group[i + 1 :]]
        cohesion.append(round(sum(sims) / len(sims), 4))
    elapsed = (time.perf_counter() - started) * 1000
    return {"groups": clusters, "cohesion": cohesion, "pair_similarity": similarity}, elapsed
