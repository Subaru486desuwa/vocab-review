import csv
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1] / "data" / "demo"
LATEST = "v2"


def _rows(name, pack=LATEST):
    with open(DEMO / pack / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _questions(pack=LATEST):
    return [json.loads(line) for line in (DEMO / pack / "questions.jsonl").read_text(encoding="utf-8").splitlines()]


def test_generated_pack_matches_source(tmp_path):
    out = tmp_path / LATEST
    subprocess.run([sys.executable, str(DEMO / "build_demo.py"), str(out)], check=True)
    for path in sorted((DEMO / LATEST).iterdir()):
        assert (out / path.name).read_text(encoding="utf-8") == path.read_text(encoding="utf-8"), path.name


def test_latest_pack_only_adds_versions_on_top_of_v1():
    """v1 已发布，不再修改：v2 中未变的题目与 v1 相同，变化的题目版本加一；正文变化的例句换 content_version。"""
    old = {q["logical_key"]: q for q in _questions("v1")}
    new = _questions()
    assert {q["logical_key"] for q in new} == set(old)
    for q in new:
        if q["version"] == old[q["logical_key"]]["version"]:
            assert q == old[q["logical_key"]], q["logical_key"]
        else:
            assert q["version"] == old[q["logical_key"]]["version"] + 1, q["logical_key"]
    assert any(q["version"] == 2 for q in new)
    old_examples = {r["example_key"]: r for r in _rows("examples.csv", "v1")}
    for r in _rows("examples.csv"):
        before = old_examples[r["example_key"]]
        assert (r["text_en"] == before["text_en"]) == (r["content_version"] == before["content_version"]), r
    assert _rows("wordbooks.csv") == _rows("wordbooks.csv", "v1")


def test_context_distractors_exclude_near_synonyms():
    groups = [{"significant", "crucial", "fundamental"}, {"diminish", "undermine"}]
    for q in _questions():
        group = next((g for g in groups if q["lemma_norm"] in g), None)
        if q["skill_type"] == "context" and group:
            assert not group & {o["text"] for o in q["options"]} - {q["lemma_norm"]}, q["logical_key"]


def test_wordbooks_share_words_and_mark_demo_source():
    books = Counter(row["wordbook_code"] for row in _rows("memberships.csv"))
    assert books == {"cet6-demo": 30, "postgraduate-demo": 30, "ielts-demo": 30}
    per_word = Counter(row["lemma_norm"] for row in _rows("memberships.csv"))
    assert sum(1 for n in per_word.values() if n == 3) == 10
    assert all(row["source"].startswith("项目自编演示 v1") for row in _rows("wordbooks.csv"))


def test_polysemous_words_have_separate_senses():
    senses = Counter(row["lemma_norm"] for row in _rows("senses.csv"))
    assert sum(1 for n in senses.values() if n > 1) >= 8


def test_every_sense_has_one_question_per_skill_type():
    per_sense = Counter((q["lemma_norm"], q["sense_key"], q["skill_type"]) for q in _questions())
    assert len(per_sense) == 3 * len(_rows("senses.csv")) and set(per_sense.values()) == {1}


def test_choice_questions_are_well_formed():
    definitions = {(r["lemma_norm"], r["sense_key"]): r["definition_zh"] for r in _rows("senses.csv")}
    for q in _questions():
        if q["skill_type"] == "spelling":
            assert q["answers"]["accepted"][0] == q["lemma_norm"]
            continue
        texts = [o["text"] for o in q["options"]]
        assert len(texts) == 4 == len(set(texts)), q["logical_key"]
        answer = next(o["text"] for o in q["options"] if o["id"] == q["answers"]["option_id"])
        if q["skill_type"] == "recognition":
            assert answer == definitions[(q["lemma_norm"], q["sense_key"])]
        else:
            assert "____" in q["prompt"] and answer.lower() == q["lemma_norm"]


def test_every_sense_has_two_examples_marked_by_key():
    examples = _rows("examples.csv")
    per_sense = Counter((r["lemma_norm"], r["sense_key"]) for r in examples)
    assert len(examples) == 2 * len(_rows("senses.csv")) and set(per_sense.values()) == {2}
    assert all(
        r["example_key"] == f"{r['lemma_norm']}-{r['sense_key']}-{n}" for r in examples for n in [r["example_key"][-1]]
    )
    assert len({r["text_en"] for r in examples}) == len(examples)
