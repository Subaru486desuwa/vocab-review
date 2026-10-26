import csv
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1] / "data" / "demo"
LATEST = "v3"
sys.path.insert(0, str(DEMO))
from build_demo import CONTEXT_SYNONYMS, SYNONYMS_V3  # noqa: E402


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


def test_v2_only_adds_versions_on_top_of_v1():
    """v1 已发布，不再修改：v2 中未变的题目与 v1 相同，变化的题目版本加一；正文变化的例句换 content_version。"""
    old = {q["logical_key"]: q for q in _questions("v1")}
    new = _questions("v2")
    assert {q["logical_key"] for q in new} == set(old)
    for q in new:
        if q["version"] == old[q["logical_key"]]["version"]:
            assert q == old[q["logical_key"]], q["logical_key"]
        else:
            assert q["version"] == old[q["logical_key"]]["version"] + 1, q["logical_key"]
    assert any(q["version"] == 2 for q in new)
    old_examples = {r["example_key"]: r for r in _rows("examples.csv", "v1")}
    for r in _rows("examples.csv", "v2"):
        before = old_examples[r["example_key"]]
        assert (r["text_en"] == before["text_en"]) == (r["content_version"] == before["content_version"]), r
    assert _rows("wordbooks.csv", "v2") == _rows("wordbooks.csv", "v1")


def test_v3_keeps_every_v2_row_and_adds_new_senses():
    """v3 只新增：v2 的题目、例句、词义与成员关系原样保留，新题目版本为 1，新例句为 demo-v3。"""
    old = {q["logical_key"]: q for q in _questions("v2")}
    new = _questions()
    assert all(q == old[q["logical_key"]] for q in new if q["logical_key"] in old) and set(old) <= {
        q["logical_key"] for q in new
    }
    assert {q["version"] for q in new if q["logical_key"] not in old} == {1}
    for name in ("examples.csv", "senses.csv", "words.csv"):
        assert _rows(name)[: len(_rows(name, "v2"))] == _rows(name, "v2"), name
    memberships = [tuple(r.values()) for r in _rows("memberships.csv")]
    assert set(tuple(r.values()) for r in _rows("memberships.csv", "v2")) <= set(memberships)
    added = [r for r in _rows("examples.csv")[len(_rows("examples.csv", "v2")) :]]
    assert added and {r["content_version"] for r in added} == {"demo-v3"}
    assert all(r["source"] == "项目自编演示 v3（AI 起草，AI 复核）" for r in added)
    assert _rows("wordbooks.csv") == _rows("wordbooks.csv", "v1")


def test_distractors_exclude_near_synonyms():
    """v1/v2 的语境题排除旧近义词组；v3 新题的辨义与语境题都排除 SYNONYMS_V3 的同组词。"""
    old = {q["logical_key"] for q in _questions("v2")}
    by_definition = {r["definition_zh"]: r["lemma_norm"] for r in _rows("senses.csv")}
    for q in _questions():
        if q["skill_type"] == "spelling":
            continue
        if q["logical_key"] in old:
            if q["skill_type"] != "context":
                continue
            groups = CONTEXT_SYNONYMS
        else:
            groups = SYNONYMS_V3
        synonyms = set().union(*(g for g in groups if q["lemma_norm"] in g)) - {q["lemma_norm"]}
        texts = {o["text"] for o in q["options"]}
        lemmas = texts if q["skill_type"] == "context" else {by_definition[t] for t in texts}
        assert not synonyms & {t.lower() for t in lemmas}, q["logical_key"]


def test_wordbooks_share_words_and_mark_demo_source():
    books = Counter(row["wordbook_code"] for row in _rows("memberships.csv"))
    assert books == {"cet6-demo": 80, "postgraduate-demo": 80, "ielts-demo": 80}
    per_word = Counter(row["lemma_norm"] for row in _rows("memberships.csv"))
    assert len(per_word) == 200 and sum(1 for n in per_word.values() if n == 3) == 20
    assert all(row["source"].startswith("项目自编演示 v1") for row in _rows("wordbooks.csv"))


def test_polysemous_words_have_separate_senses():
    senses = Counter(row["lemma_norm"] for row in _rows("senses.csv"))
    assert sum(1 for n in senses.values() if n > 1) >= 14
    definitions = [row["definition_zh"] for row in _rows("senses.csv")]
    assert len(definitions) == len(set(definitions))


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
