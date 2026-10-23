import csv
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1] / "data" / "demo"


def _rows(name):
    with open(DEMO / "v1" / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _questions():
    return [json.loads(line) for line in (DEMO / "v1" / "questions.jsonl").read_text(encoding="utf-8").splitlines()]


def test_generated_pack_matches_source(tmp_path):
    subprocess.run([sys.executable, str(DEMO / "build_demo.py"), str(tmp_path)], check=True)
    for path in sorted((DEMO / "v1").iterdir()):
        assert (tmp_path / path.name).read_text(encoding="utf-8") == path.read_text(encoding="utf-8"), path.name


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
