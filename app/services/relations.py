"""词对（ADR 0004）：近义、派生、形近。内容关系，只用于展示与用户主动发起的成对练习，不改变组卷与复习安排。"""

from collections import defaultdict

from app.repositories import relations as repo

# 展示顺序：形近最容易混，其次近义，再次同族。
RELATION_TYPES = ("confusable", "synonym", "derivation")
PER_WORD = 6


def related(conn, word_ids, limit=PER_WORD):
    """word_id → 词对列表 [{word_id, lemma, types, senses: [{sense_id, part_of_speech, definition_zh}]}]。

    同一对词的多种关系合并为一项；按最靠前的关系类型、再按词条排序，每个词最多 limit 项（None 不限）。
    """
    rows = repo.partners(conn, set(word_ids))
    senses = defaultdict(list)
    for s in repo.word_senses(conn, {r["partner_id"] for r in rows}):
        senses[s["word_id"]].append({k: s[k] for k in ("sense_id", "part_of_speech", "definition_zh")})
    grouped = defaultdict(dict)
    for r in rows:
        entry = grouped[r["word_id"]].setdefault(
            r["partner_id"],
            {"word_id": r["partner_id"], "lemma": r["partner_lemma"], "types": [], "senses": senses[r["partner_id"]]},
        )
        entry["types"].append(r["relation_type"])
    result = {}
    for word_id, entries in grouped.items():
        for e in entries.values():
            e["types"].sort(key=RELATION_TYPES.index)
        ordered = sorted(entries.values(), key=lambda e: (RELATION_TYPES.index(e["types"][0]), e["lemma"]))
        result[word_id] = ordered if limit is None else ordered[:limit]
    return result


def pair_types(conn, pairs):
    """(word_id, word_id) → 两词之间的关系类型列表；无关系的对不出现。"""
    found = {}
    by_word = defaultdict(set)
    for a, b in pairs:
        by_word[a].add(b)
    for r in repo.partners(conn, set(by_word)):
        if r["partner_id"] in by_word[r["word_id"]]:
            found.setdefault((r["word_id"], r["partner_id"]), []).append(r["relation_type"])
    return {k: sorted(v, key=RELATION_TYPES.index) for k, v in found.items()}
