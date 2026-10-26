"""由 source/ 生成可导入的演示内容包。

用法：python data/demo/build_demo.py [输出目录]，默认写入 data/demo/v3，并与已发布的 data/demo/v2 比对：
内容变化的题目版本号加一，正文变化的例句换用新的 content_version，未变的行与 v2 完全相同。
v1、v2 已发布，保持不变；新库依次导入 v1、v2、v3。
source/entries.csv 是 v1/v2 的词义，只在这些词义里取干扰项，因此 v3 不改变已有题目；
source/entries_v3.csv 是 v3 新增的词义，从全部词义里取干扰项，辨义与语境题都排除同组近义词。
校对只改 source/ 下的表，再重新生成；同一输入总是得到同一输出（干扰项按题目键固定随机）。
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
SOURCE_V3 = "项目自编演示 v3（AI 起草，AI 复核）"
VERSION = "v1"
CONTENT_VERSION = "demo-v1"
CONTENT_VERSION_V3 = "demo-v3"
LATEST = "v3"
BASELINE = HERE / "v2"
# 语境题干扰项排除近义词：同组词填入同一句子都成立，会让题目出现多个正确答案。
CONTEXT_SYNONYMS = [{"significant", "crucial", "fundamental"}, {"diminish", "undermine"}]
# v3 新词义的近义词组：辨义与语境题都不把同组词作为干扰项（可含 v1/v2 的词条）。
SYNONYMS_V3 = [
    {"mitigate", "alleviate"},
    {"substantial", "abundant", "immense"},
    {"comprehensive", "substantial", "radical"},
    {"significant", "crucial", "fundamental", "indispensable"},
    {"diminish", "undermine", "erode"},
    {"constrain", "hinder"},
    {"devote", "allocate"},
    {"inherent", "inevitable"},
    {"disparity", "discrepancy"},
    {"prevalent", "dominant", "prominent"},
    {"sustainable", "renewable"},
    {"boost", "stimulate", "facilitate"},
    {"cautious", "optimistic", "skeptical"},
    {"cultivate", "reinforce", "cherish"},
    {"exploit", "utilize"},
    {"magnify", "exaggerate"},
    {"modest", "humble"},
    {"feasible", "plausible", "rational"},
    {"rational", "coherent", "fair"},
    {"contradict", "refute", "constrain"},
    {"deduce", "verify", "assume"},
    {"marginal", "subtle"},
    {"retain", "maintain"},
    {"ambition", "objective"},
    {"dilemma", "paradox"},
    {"paradox", "phenomenon"},
    {"tentative", "preliminary"},
    {"affordable", "budget"},
    {"urban", "residential"},
    {"fertile", "humid"},
    {"suburb", "neighbourhood"},
    {"agriculture", "tourism", "infrastructure", "conservation"},
    {"wildlife", "biodiversity", "habitat"},
    {"fossil", "habitat"},
    {"carbon", "pollution", "emission"},
    {"drought", "pollution"},
    {"pedestrian", "vegetarian"},
    {"semester", "lecture"},
    {"assume", "perceive"},
]
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


def build_questions(entries, pool=None, synonym_groups=None):
    """pool 为取干扰项的词义（默认 entries）。给定 synonym_groups 时辨义题也排除同组近义词；
    否则只在语境题排除 CONTEXT_SYNONYMS（v1/v2 的规则，保持已发布题目不变）。"""
    pool = entries if pool is None else pool
    groups = CONTEXT_SYNONYMS if synonym_groups is None else synonym_groups
    questions = []
    for e in entries:
        base = f"{e['lemma_norm']}-{e['sense_key']}"
        synonyms = set().union(*(g for g in groups if e["lemma_norm"] in g))
        same_pos = [
            o for o in pool if o["part_of_speech"] == e["part_of_speech"] and o["lemma_norm"] != e["lemma_norm"]
        ]
        recognition_pool = same_pos
        if synonym_groups is not None:
            recognition_pool = [o for o in same_pos if o["lemma_norm"] not in synonyms]

        key = f"{base}-recognition"
        options, answer = _choice_options(
            random.Random(key), e["definition_zh"], [o["definition_zh"] for o in recognition_pool]
        )
        questions.append(_question(key, e, "recognition", f"{e['lemma']}（{e['part_of_speech']}）", options, answer))

        key = f"{base}-context"
        sentence = e["example_en"]
        article = sentence[: TARGET.search(sentence).start()].split()[-1:]
        candidates = [o["lemma"] for o in same_pos if o["lemma_norm"] not in synonyms]
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


def load_extra_examples(path, entries):
    """每个词义的补充例句（DL 语料）；必须对应 entries.csv 中已有的词义，且用 [...] 标出目标词。"""
    known = {(e["lemma_norm"], e["sense_key"]) for e in entries}
    extra = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            key = (normalize(row["lemma"]), row["sense_key"])
            if key not in known or len(TARGET.findall(row["example_en"])) != 1:
                raise ValueError(f"补充例句无效：{row}")
            extra.setdefault(key, []).append(row)
    return extra


def _example_rows(entries, extra, source=SOURCE, content_version=CONTENT_VERSION):
    rows = []
    for e in entries:
        sentences = [(e["example_en"], e["example_zh"])]
        sentences += [(x["example_en"], x["example_zh"]) for x in extra.get((e["lemma_norm"], e["sense_key"]), [])]
        for n, (text, translation) in enumerate(sentences, start=1):
            key = f"{e['lemma_norm']}-{e['sense_key']}-{n}"
            rows.append(
                (key, e["lemma_norm"], e["sense_key"], TARGET.sub(r"\1", text), translation, source, content_version, 1)
            )
    return rows


def apply_baseline(questions, example_rows, baseline, content_version):
    """与已发布的内容包比对：题目内容变化则版本加一，例句正文变化则换用 content_version。"""
    old_questions = {}
    for line in (baseline / "questions.jsonl").read_text(encoding="utf-8").splitlines():
        q = json.loads(line)
        old_questions[q["logical_key"]] = q
    for q in questions:
        old = old_questions.get(q["logical_key"])
        if old is not None:
            changed = any(old[k] != q[k] for k in ("prompt", "options", "answers", "grading_policy"))
            q["version"] = old["version"] + 1 if changed else old["version"]
    with open(baseline / "examples.csv", encoding="utf-8", newline="") as f:
        old_examples = {row["example_key"]: row for row in csv.DictReader(f)}
    rows = []
    for row in example_rows:
        old = old_examples.get(row[0])
        if old is not None:
            row = (*row[:6], old["content_version"] if old["text_en"] == row[3] else content_version, *row[7:])
        rows.append(row)
    return rows


def build(
    out_dir,
    entries_path=HERE / "source" / "entries.csv",
    extra_path=HERE / "source" / "extra_examples.csv",
    baseline=BASELINE,
    new_entries_path=HERE / "source" / "entries_v3.csv",
    new_extra_path=HERE / "source" / "extra_examples_v3.csv",
):
    old_entries = load_entries(entries_path)
    old_extra = load_extra_examples(extra_path, old_entries)
    new_entries = load_entries(new_entries_path) if new_entries_path else []
    new_extra = load_extra_examples(new_extra_path, new_entries) if new_entries else {}
    entries = old_entries + new_entries
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
    questions = build_questions(old_entries) + build_questions(new_entries, entries, SYNONYMS_V3)
    examples = _example_rows(old_entries, old_extra) + _example_rows(
        new_entries, new_extra, SOURCE_V3, CONTENT_VERSION_V3
    )
    if baseline is not None:
        examples = apply_baseline(questions, examples, Path(baseline), f"demo-{out.name}")
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
        examples,
    )
    with open(out / "questions.jsonl", "w", encoding="utf-8") as f:
        for q in questions:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else HERE / LATEST)
