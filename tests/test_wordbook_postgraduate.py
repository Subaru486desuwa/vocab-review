"""考研词表内容包（ADR 0004）：结构自洽，并能在演示内容之上导入。原始数据不在仓库中，这里不重新构建。"""

import csv
import json
from collections import Counter
from pathlib import Path

import pytest

from app.services.content_import import RELATION_TYPES, import_content, read_directory
from tests.helpers import NOW

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "data" / "wordbooks" / "postgraduate" / "v1"
DEMO = ROOT / "data" / "demo"


def rows(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def questions():
    with open(PACK / "questions.jsonl", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def test_pack_references_are_consistent():
    demo_words = {r["lemma_norm"] for r in rows(DEMO / "v3" / "words.csv")}
    words = {r["lemma_norm"] for r in rows(PACK / "words.csv")}
    assert not words & demo_words, "演示词条沿用原有内容，不重复写入"
    members = [r["lemma_norm"] for r in rows(PACK / "memberships.csv")]
    assert len(members) == len(set(members)) and set(members) <= words | demo_words
    assert [int(r["position"]) for r in rows(PACK / "memberships.csv")] == list(range(1, len(members) + 1))
    senses = {(r["lemma_norm"], r["sense_key"]) for r in rows(PACK / "senses.csv")}
    assert {lemma for lemma, _ in senses} == words
    qs = questions()
    assert {(q["lemma_norm"], q["sense_key"]) for q in qs} == senses
    by_skill = Counter((q["lemma_norm"], q["sense_key"], q["skill_type"]) for q in qs)
    assert max(by_skill.values()) == 1
    assert all((lemma, key, "recognition") in by_skill for lemma, key in senses), "每个词义都有辨义题"
    for r in rows(PACK / "examples.csv"):
        assert (r["lemma_norm"], r["sense_key"]) in senses and r["source"].startswith("Tatoeba #")


def test_choice_questions_have_four_distinct_options_and_one_answer():
    for q in questions():
        if q["skill_type"] == "spelling":
            assert q["answers"]["accepted"] == [q["lemma_norm"]]
            continue
        texts = [o["text"] for o in q["options"]]
        assert len(texts) == 4 and len(set(texts)) == 4, q["logical_key"]
        answer = next(o["text"] for o in q["options"] if o["id"] == q["answers"]["option_id"])
        if q["skill_type"] == "context":
            assert answer == q["lemma_norm"] and q["prompt"].count("____") == 1


def test_spelling_prompts_are_unique_across_demo_and_pack():
    prompts = [q["prompt"] for q in questions() if q["skill_type"] == "spelling"]
    with open(DEMO / "v3" / "questions.jsonl", encoding="utf-8") as f:
        prompts += [q["prompt"] for q in map(json.loads, f) if q["skill_type"] == "spelling"]
    assert len(prompts) == len(set(prompts))


def test_relations_are_unordered_unique_pairs_within_the_book():
    book = {r["lemma_norm"] for r in rows(PACK / "memberships.csv")}
    keys = set()
    for r in rows(PACK / "relations.csv"):
        a, b, t = r["lemma_norm_a"], r["lemma_norm_b"], r["relation_type"]
        assert a < b and {a, b} <= book and t in RELATION_TYPES
        assert (a, b, t) not in keys
        keys.add((a, b, t))
    assert {("adapt", "adopt", "confusable"), ("affect", "effect", "confusable")} <= keys


@pytest.mark.db
def test_pack_imports_over_demo_content(db_conn):
    for pack in ("v1", "v2", "v3"):
        import_content(db_conn, read_directory(DEMO / pack), NOW)
    summary = import_content(db_conn, read_directory(PACK), NOW)
    expected = {
        "wordbooks": 1,
        "words": len(rows(PACK / "words.csv")),
        "senses": len(rows(PACK / "senses.csv")),
        "memberships": len(rows(PACK / "memberships.csv")),
        "examples": len(rows(PACK / "examples.csv")),
        "questions": len(questions()),
        "relations": len(rows(PACK / "relations.csv")),
    }
    assert {name: s["inserted"] for name, s in summary.items()} == expected
    assert all(s["updated"] == 0 for s in summary.values()), "演示内容不被改写"
