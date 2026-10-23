"""由 source/entries.csv 生成可导入的演示内容包 v1。

用法：python data/demo/build_demo.py [输出目录]，默认写入 data/demo/v1。
校对只改 entries.csv，再重新生成；同一输入总是得到同一输出（干扰项按题目键固定随机）。
"""

import csv
import json
import random
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = "项目自编演示 v1（AI 起草，待人工校对）"
VERSION = "v1"
CONTENT_VERSION = "demo-v1"
WORDBOOKS = [
    ("cet6-demo", "cet6", "六级演示词表"),
    ("postgraduate-demo", "postgraduate", "考研演示词表"),
    ("ielts-demo", "ielts", "雅思演示词表"),
]
OPTION_IDS = "abcd"
TARGET = re.compile(r"\[([^\]]+)\]")


def normalize(lemma):
    return " ".join(unicodedata.normalize("NFC", lemma).strip().lower().split())


def load_entries(path):
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["lemma_norm"] = normalize(row["lemma"])
        row["books"] = row["books"].split()
        row["variants"] = [v for v in row["spelling_variants"].split("|") if v]
    return rows


def _choice_options(rng, correct, candidates):
    picked = rng.sample(sorted(set(candidates)), 3)
    texts = [correct, *picked]
    rng.shuffle(texts)
    options = [{"id": OPTION_IDS[i], "text": text} for i, text in enumerate(texts)]
    return options, OPTION_IDS[texts.index(correct)]


def _starts_with_vowel(word):
    return word[0].lower() in "aeiou"


def build_questions(entries):
    questions = []
    for e in entries:
        base = f"{e['lemma_norm']}-{e['sense_key']}"
        same_pos = [
            o for o in entries if o["part_of_speech"] == e["part_of_speech"] and o["lemma_norm"] != e["lemma_norm"]
        ]

        key = f"{base}-recognition"
        options, answer = _choice_options(
            random.Random(key), e["definition_zh"], [o["definition_zh"] for o in same_pos]
        )
        questions.append(_question(key, e, "recognition", f"{e['lemma']}（{e['part_of_speech']}）", options, answer))

        key = f"{base}-context"
        sentence = e["example_en"]
        article = sentence[: TARGET.search(sentence).start()].split()[-1:]
        candidates = [o["lemma"] for o in same_pos]
        if article and article[0].lower() in ("a", "an"):
            # 冠词 a/an 不应暗示答案，只取首字母元音性一致的干扰词。
            candidates = [c for c in candidates if _starts_with_vowel(c) == _starts_with_vowel(e["lemma"])]
        options, answer = _choice_options(random.Random(key), e["lemma"], candidates)
        questions.append(_question(key, e, "context", TARGET.sub("____", sentence), options, answer))

        key = f"{base}-spelling"
        prompt = f"{e['definition_zh']}（{e['part_of_speech']}），首字母 {e['lemma'][0]}"
        questions.append(
            {
                "logical_key": key,
                "version": 1,
                "lemma_norm": e["lemma_norm"],
                "sense_key": e["sense_key"],
                "skill_type": "spelling",
                "prompt": prompt,
                "options": None,
                "answers": {"accepted": [e["lemma"], *e["variants"]]},
                "grading_policy": {"type": "text", "trim": True, "case_sensitive": False},
                "status": "published",
            }
        )
    return questions


def _question(key, e, skill_type, prompt, options, answer):
    return {
        "logical_key": key,
        "version": 1,
        "lemma_norm": e["lemma_norm"],
        "sense_key": e["sense_key"],
        "skill_type": skill_type,
        "prompt": prompt,
        "options": options,
        "answers": {"option_id": answer},
        "grading_policy": {"type": "choice"},
        "status": "published",
    }


def _write_csv(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def build(out_dir, entries_path=HERE / "source" / "entries.csv"):
    entries = load_entries(entries_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(
        out / "wordbooks.csv",
        ["code", "version", "exam_type", "name", "source", "is_active"],
        [(code, VERSION, exam, name, SOURCE, 1) for code, exam, name in WORDBOOKS],
    )
    words = {}
    for e in entries:
        words.setdefault(e["lemma_norm"], e)
    _write_csv(
        out / "words.csv",
        ["language", "lemma", "lemma_norm", "phonetic", "is_active"],
        [("en", e["lemma"], norm, "", 1) for norm, e in words.items()],
    )
    _write_csv(
        out / "senses.csv",
        ["lemma_norm", "sense_key", "part_of_speech", "definition_zh", "definition_en", "is_active"],
        [
            (e["lemma_norm"], e["sense_key"], e["part_of_speech"], e["definition_zh"], e["definition_en"], 1)
            for e in entries
        ],
    )
    memberships = []
    for code, exam, _ in WORDBOOKS:
        in_book = [norm for norm, e in words.items() if exam in e["books"]]
        memberships += [(code, VERSION, norm, i, "") for i, norm in enumerate(in_book, start=1)]
    _write_csv(
        out / "memberships.csv",
        ["wordbook_code", "wordbook_version", "lemma_norm", "position", "source_note"],
        memberships,
    )
    _write_csv(
        out / "examples.csv",
        [
            "example_key",
            "lemma_norm",
            "sense_key",
            "text_en",
            "translation_zh",
            "source",
            "content_version",
            "is_active",
        ],
        [
            (
                f"{e['lemma_norm']}-{e['sense_key']}-1",
                e["lemma_norm"],
                e["sense_key"],
                TARGET.sub(r"\1", e["example_en"]),
                e["example_zh"],
                SOURCE,
                CONTENT_VERSION,
                1,
            )
            for e in entries
        ],
    )
    with open(out / "questions.jsonl", "w", encoding="utf-8") as f:
        for q in build_questions(entries):
            f.write(json.dumps(q, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else HERE / VERSION)
