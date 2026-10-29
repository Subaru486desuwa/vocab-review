"""由 ECDICT、WordNet 3.0 与 Tatoeba 生成考研词表内容包（ADR 0004）。

用法：python data/wordbooks/postgraduate/build.py [原始数据目录] [输出目录]，默认读 data/raw、写 v1/。
原始数据不进 Git，下载方式见同目录 README.md；词性标注需要 nltk（只在构建时使用，不是应用依赖）。
同一原始数据总是得到同一输出：干扰项按题目键固定随机，例句按句子编号排序选取。
已在演示词库（data/demo/v3）中的词条只加入词表成员，沿用原有词义与题目。
"""

import bz2
import csv
import json
import random
import re
import sys
import tarfile
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEMO = ROOT / "data" / "demo" / "v3"

CODE, VERSION, EXAM_TYPE = "ky-ecdict", "v1", "postgraduate"
NAME = "考研词表（ECDICT）"
SOURCE = "ECDICT 考研标签（skywind3000/ECDICT，MIT）；词义按词性拆分，题目规则生成，未逐条复核"
CONTENT_VERSION = "ky-v1"
WORDNET_SOURCE = "WordNet 3.0"
CONFUSABLE_SOURCE = "拼写编辑距离"

MAX_SENSES = 3
MAX_ITEMS = 4
EXAMPLES_PER_SENSE = 2
SENTENCE_WORDS = (6, 18)
# WordNet 同义词集只取两个词各自最常用的前几个、且在语料中标注过的义项，避免冷僻义项连出的近义词。
SYNONYM_TOP_SENSES = 2
SYNONYM_MIN_TAGGED = 1

# ECDICT 词性 → 显示词性；vt./vi. 合并为 v.，sense_key 为去掉点的词性。
POS = {
    "n": "n.", "v": "v.", "vt": "v.", "vi": "v.", "a": "adj.", "adj": "adj.", "adv": "adv.",
    "prep": "prep.", "conj": "conj.", "pron": "pron.", "num": "num.", "interj": "int.", "int": "int.",
}  # fmt: skip
POS_FAMILY = {"n.": "n", "v.": "v", "adj.": "adj", "adv.": "adv"}
# ECDICT 英文释义行首的词性字母
EN_POS = {"n": "n", "v": "v", "a": "adj", "s": "adj", "j": "adj", "r": "adv"}
# NLTK Penn 标签 → 词性族；只用原形对应的标签。
TAG_FAMILY = {"NN": "n", "VB": "v", "VBP": "v", "JJ": "adj", "RB": "adv"}
WN_FILES = {"noun": "n", "verb": "v", "adj": "adj", "adv": "adv"}


# ---- ECDICT ----


def clean_items(text):
    items = []
    for item in re.split(r"[,，;；]", text):
        item = re.sub(r"\s+", "", item).strip("。.")
        if item and item not in items and not re.fullmatch(r"[\W\d_]+", item):
            items.append(item)
    return items[:MAX_ITEMS]


def parse_senses(translation, tagged):
    """按词性行拆分中文释义，同词性（含 vt./vi.）的各行轮流取释义合并，最多 MAX_SENSES 个。

    第一个词性总保留；之后的实词词性在 WordNet 语料中没有标注过（tagged 为 0）时视为冷僻用法，跳过。
    """
    lines = defaultdict(list)
    for line in translation.split("\\n"):
        m = re.match(r"([a-z]+)\.\s*(.+)", line.strip())
        if m and m.group(1) in POS and (items := clean_items(m.group(2))):
            lines[POS[m.group(1)]].append(items)
    senses = []
    for pos, groups in lines.items():
        if senses and POS_FAMILY.get(pos) and not tagged.get(POS_FAMILY[pos]):
            continue
        merged = []
        for column in range(max(len(g) for g in groups)):
            merged.extend(g[column] for g in groups if column < len(g) and g[column] not in merged)
        senses.append((pos, "；".join(merged[:MAX_ITEMS])))
    return senses[:MAX_SENSES]


def parse_definitions_en(definition):
    """英文释义按词性族取第一条。"""
    found = {}
    for line in definition.split("\\n"):
        m = re.match(r"([a-z])\.?\s+(.+)", line.strip())
        if m and m.group(1) in EN_POS:
            # WordNet 释义分号后是用例引文，只保留释义本身。
            found.setdefault(EN_POS[m.group(1)], m.group(2).split(";")[0].strip()[:500])
    return found


def inflections(exchange):
    return {part.split(":", 1)[1] for part in exchange.split("/") if ":" in part}


def load_ecdict(raw):
    rows = {}
    with open(raw / "ecdict" / "ecdict.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            word = r["word"]
            if "ky" not in (r["tag"] or "").split() or not re.fullmatch(r"[a-z]+(-[a-z]+)*", word):
                continue
            rows[word] = r
    return rows


# ---- WordNet ----


def load_wordnet(raw):
    """返回 (synsets, ranks)。

    synsets[(pos, offset)] = (词列表, 派生指针)；ranks[(词, pos, offset)] = (义项序号, 语料标注次数)。
    """
    synsets, ranks = {}, {}
    with tarfile.open(raw / "wordnet" / "WNdb-3.0.tar.gz") as tar:
        for name, pos in WN_FILES.items():
            for line in tar.extractfile(f"dict/data.{name}").read().decode("latin-1").splitlines():
                if line.startswith(" "):
                    continue
                parts = line.split(" | ")[0].split()
                offset, count = parts[0], int(parts[3], 16)
                words = [parts[4 + 2 * i].lower().split("(")[0] for i in range(count)]
                rest = parts[4 + 2 * count :]
                pointers = []
                for i in range(int(rest[0])):
                    symbol, target, target_pos, st = rest[1 + 4 * i : 5 + 4 * i]
                    if symbol == "+":
                        target_key = (WN_FILES[_WN_POS[target_pos]], target)
                        pointers.append((int(st[:2], 16) - 1, target_key, int(st[2:], 16) - 1))
                synsets[(pos, offset)] = (words, pointers)
        for line in tar.extractfile("dict/index.sense").read().decode("latin-1").splitlines():
            key, offset, number, tagged = line.split()
            lemma, rest = key.split("%")
            pos = {"1": "n", "2": "v", "3": "adj", "4": "adv", "5": "adj"}[rest[0]]
            ranks[(lemma, pos, offset)] = (int(number), int(tagged))
    return synsets, ranks


def _common(rank):
    return rank is not None and rank[0] <= SYNONYM_TOP_SENSES and rank[1] >= SYNONYM_MIN_TAGGED


_WN_POS = {"n": "noun", "v": "verb", "a": "adj", "s": "adj", "r": "adv"}


def wordnet_relations(book, synsets, ranks):
    pairs = {}
    for (pos, offset), (words, pointers) in synsets.items():
        members = sorted({w for w in words if w in book})
        for i, a in enumerate(members):
            for b in members[i + 1 :]:
                if all(_common(ranks.get((w, pos, offset))) for w in (a, b)):
                    pairs[(a, b, "synonym")] = WORDNET_SOURCE
        for source, target, target_index in pointers:
            target_words = synsets.get(target, ([], []))[0]
            if 0 <= source < len(words) and 0 <= target_index < len(target_words):
                a, b = words[source], target_words[target_index]
                if a != b and a in book and b in book:
                    pairs[(*sorted((a, b)), "derivation")] = WORDNET_SOURCE
    return pairs


# ---- 形近 ----


def edit_distance(a, b):
    """Damerau–Levenshtein（相邻换位算一次），与 app/services/insights.py 同一定义。"""
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


def _deletions(word, depth):
    keys = {word}
    for _ in range(depth):
        keys |= {k[:i] + k[i + 1 :] for k in keys for i in range(len(k))}
    return keys


PREFIXES = ("un", "in", "im", "il", "ir", "dis", "non", "mis")


def confusable_pairs(book, forms, family):
    """拼写相近的词对：长度 ≥4 距离为 1，或长度 ≥8、前三个字母相同且距离为 2；不超过 5 个字母的词只差首字母不算。

    排除词形变化、仅差词尾或前缀（un-、in-、dis- 等）的组合；同族词只保留等长的一处之差（如 advice/advise）。
    """
    buckets = defaultdict(set)
    for word in book:
        if len(word) >= 4:
            for key in _deletions(word, 2 if len(word) >= 7 else 1):
                buckets[key].add(word)
    pairs = {}
    for members in buckets.values():
        for a in members:
            for b in members:
                if a >= b or (a, b, "confusable") in pairs:
                    continue
                distance = edit_distance(a, b)
                if distance > (2 if min(len(a), len(b)) >= 8 and a[:3] == b[:3] else 1):
                    continue
                if b in forms[a] or a in forms[b]:
                    continue
                # 短词只差首字母多是押韵词（fate/mate），不算形近。
                if len(a) == len(b) <= 5 and a[1:] == b[1:]:
                    continue
                if b in family[a] and (distance > 1 or len(a) != len(b)):
                    continue
                short, long_ = sorted((a, b), key=len)
                if long_.startswith(short) and long_[len(short) :] in ("s", "es", "d", "ed", "r", "er", "ly", "y"):
                    continue
                if long_.endswith(short) and long_[: -len(short)] in PREFIXES:
                    continue
                pairs[(a, b, "confusable")] = CONFUSABLE_SOURCE
    return pairs


# ---- Tatoeba ----


def load_tatoeba(raw):
    def rows(name):
        with bz2.open(raw / "tatoeba" / name, "rt", encoding="utf-8") as f:
            for line in f:
                yield line.rstrip("\n").split("\t")

    cmn = {int(p[0]): p[2] for p in rows("cmn_sentences.tsv.bz2")}
    links = defaultdict(list)
    for a, b in rows("eng-cmn_links.tsv.bz2"):
        if int(b) in cmn:
            links[int(a)].append(int(b))
    pairs = []
    for p in rows("eng_sentences.tsv.bz2"):
        sid = int(p[0])
        if sid in links:
            zh_id = min(links[sid])
            pairs.append((sid, p[2], zh_id, cmn[zh_id]))
    return sorted(pairs)


TOKEN = re.compile(r"[A-Za-z]+(?:[-'][A-Za-z]+)*|[^\sA-Za-z]")


def find_examples(pairs, wanted):
    """wanted[lemma] = {词性族}；返回 examples[(lemma, 词性族)] = [(eng_id, text, zh_id, zh, 词前一词)]。"""
    import nltk

    found = defaultdict(list)
    candidates = []
    for sid, text, zh_id, zh in pairs:
        words = text.split()
        if not (SENTENCE_WORDS[0] <= len(words) <= SENTENCE_WORDS[1]) or len(text) > 140 or '"' in text:
            continue
        tokens = TOKEN.findall(text)
        lowered = [t.lower() for t in tokens]
        hits = [w for w in set(lowered) if w in wanted and lowered.count(w) == 1 and lowered.index(w) > 0]
        if hits:
            candidates.append((sid, text, zh_id, zh, tokens, hits))
    tagged = nltk.pos_tag_sents([c[4] for c in candidates])
    for (sid, text, zh_id, zh, tokens, hits), tags in zip(candidates, tagged, strict=True):
        lowered = [t.lower() for t in tokens]
        for lemma in hits:
            i = lowered.index(lemma)
            family = TAG_FAMILY.get(tags[i][1])
            if tokens[i] != lemma or family not in wanted[lemma]:
                continue
            found[(lemma, family)].append((sid, text, zh_id, zh, lowered[i - 1]))
    return found


def pick_examples(options):
    """偏好 10 词左右的句子，同长度按句子编号。"""
    return sorted(options, key=lambda o: (abs(len(o[1].split()) - 10), o[0]))[:EXAMPLES_PER_SENSE]


def blank(text, lemma):
    tokens = TOKEN.findall(text)
    index = [t.lower() for t in tokens].index(lemma)
    start = 0
    for t in tokens[:index]:
        start = text.index(t, start) + len(t)
    at = text.index(tokens[index], start)
    return text[:at] + "____" + text[at + len(lemma) :]


# ---- 题目 ----


def overlaps(a, b):
    items_a, items_b = set(a.split("；")), set(b.split("；"))
    return bool(items_a & items_b) or any(x in y or y in x for x in items_a for y in items_b)


def recognition(sense, all_senses, related, rng):
    lemma, pos, zh = sense["lemma"], sense["pos"], sense["zh"]
    excluded = related["synonym"][lemma] | {lemma}
    usable = [s for s in all_senses if s["lemma"] not in excluded and not overlaps(s["zh"], zh) and len(s["zh"]) <= 40]
    same_pos = [s for s in usable if s["pos"] == pos]
    confusable = sorted(
        (s for s in same_pos if s["lemma"] in related["confusable"][lemma]), key=lambda s: (s["lemma"], s["key"])
    )
    chosen = []
    for s in rng.sample(confusable, min(2, len(confusable))):
        if not any(overlaps(s["zh"], c) for c in chosen):
            chosen.append(s["zh"])
    while len(chosen) < 3:
        s = rng.choice(same_pos)
        if s["zh"] not in chosen and not any(overlaps(s["zh"], c) for c in chosen):
            chosen.append(s["zh"])
    return _choice_question(sense, "recognition", f"{lemma}（{pos}）", zh, chosen, rng)


def context(sense, example, words_by_family, related, rng):
    lemma = sense["lemma"]
    family = POS_FAMILY[sense["pos"]]
    previous = example[4]
    excluded = related["synonym"][lemma] | related["derivation"][lemma] | {lemma}

    def fits(word):
        if word in excluded:
            return False
        if previous in ("a", "an"):
            return (word[0] in "aeiou") == (lemma[0] in "aeiou")
        return True

    pool = [w for w in words_by_family[family] if fits(w)]
    confusable = sorted(w for w in related["confusable"][lemma] if w in set(pool))
    chosen = rng.sample(confusable, min(2, len(confusable)))
    while len(chosen) < 3:
        word = rng.choice(pool)
        if word not in chosen:
            chosen.append(word)
    return _choice_question(sense, "context", blank(example[1], lemma), lemma, chosen, rng)


def _choice_question(sense, skill, prompt, answer, distractors, rng):
    texts = [answer, *distractors]
    rng.shuffle(texts)
    options = [{"id": "abcd"[i], "text": t} for i, t in enumerate(texts)]
    return {
        **_question_head(sense, skill),
        "prompt": prompt,
        "options": options,
        "answers": {"option_id": "abcd"[texts.index(answer)]},
        "grading_policy": {"type": "choice"},
        "status": "published",
    }


def spelling(sense):
    return {
        **_question_head(sense, "spelling"),
        "prompt": spelling_prompt(sense),
        "options": None,
        "answers": {"accepted": [sense["lemma"]]},
        "grading_policy": {"type": "text", "trim": True, "case_sensitive": False},
        "status": "published",
    }


def spelling_prompt(sense):
    return f"{sense['zh']}（{sense['pos']}），首字母 {sense['lemma'][0]}"


def _question_head(sense, skill):
    return {
        "logical_key": f"ky-{sense['lemma']}-{sense['key']}-{skill}",
        "version": 1,
        "lemma_norm": sense["lemma"],
        "sense_key": sense["key"],
        "skill_type": skill,
    }


# ---- 输出 ----

EXAMPLE_COLUMNS = [
    "example_key", "lemma_norm", "sense_key", "text_en", "translation_zh", "source", "content_version", "is_active",
]  # fmt: skip


def read_demo():
    with open(DEMO / "words.csv", encoding="utf-8") as f:
        words = {r["lemma_norm"] for r in csv.DictReader(f)}
    prompts = set()
    with open(DEMO / "questions.jsonl", encoding="utf-8") as f:
        for line in f:
            q = json.loads(line)
            if q["skill_type"] == "spelling":
                prompts.add(q["prompt"])
    return words, prompts


def write_csv(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def build(raw, out):
    ecdict = load_ecdict(raw)
    demo_words, demo_prompts = read_demo()
    synsets, ranks = load_wordnet(raw)
    tagged = defaultdict(lambda: defaultdict(int))
    for (lemma, pos, _), (_, count) in ranks.items():
        tagged[lemma][pos] += count
    senses, en = [], {}
    for word in sorted(ecdict):
        if word in demo_words:
            continue
        en[word] = parse_definitions_en(ecdict[word]["definition"])
        for pos, zh in parse_senses(ecdict[word]["translation"], tagged[word]):
            senses.append({"lemma": word, "pos": pos, "key": pos.rstrip("."), "zh": zh})
    has_sense = {s["lemma"] for s in senses}
    book = sorted(w for w in ecdict if w in has_sense or w in demo_words)
    book_set = set(book)
    forms = {w: inflections(ecdict[w]["exchange"]) for w in book}

    relations = wordnet_relations(book_set, synsets, ranks)
    family = defaultdict(set)
    for a, b, t in relations:
        if t == "derivation":
            family[a].add(b)
            family[b].add(a)
    relations.update(confusable_pairs(book_set, forms, family))
    related = {t: defaultdict(set) for t in ("synonym", "derivation", "confusable")}
    for a, b, t in relations:
        related[t][a].add(b)
        related[t][b].add(a)

    wanted = defaultdict(set)
    for s in senses:
        if s["pos"] in POS_FAMILY:
            wanted[s["lemma"]].add(POS_FAMILY[s["pos"]])
    found = find_examples(load_tatoeba(raw), wanted)

    words_by_family = defaultdict(set)
    for s in senses:
        if s["pos"] in POS_FAMILY:
            words_by_family[POS_FAMILY[s["pos"]]].add(s["lemma"])
    words_by_family = {k: sorted(v) for k, v in words_by_family.items()}

    prompt_count = defaultdict(int)
    for s in senses:
        prompt_count[spelling_prompt(s)] += 1

    questions, examples = [], []
    for s in senses:
        rng = random.Random(f"ky-{s['lemma']}-{s['key']}")
        questions.append(recognition(s, senses, related, rng))
        family = POS_FAMILY.get(s["pos"])
        chosen = pick_examples(found.get((s["lemma"], family), [])) if family else []
        for n, ex in enumerate(chosen, start=1):
            source = f"Tatoeba #{ex[0]} / #{ex[2]}（CC BY 2.0 FR）"
            key = f"ky-{s['lemma']}-{s['key']}-{n}"
            examples.append([key, s["lemma"], s["key"], ex[1], ex[3], source, CONTENT_VERSION, 1])
        if chosen:
            questions.append(context(s, chosen[0], words_by_family, related, rng))
        prompt = spelling_prompt(s)
        if prompt_count[prompt] == 1 and prompt not in demo_prompts:
            questions.append(spelling(s))

    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "wordbooks.csv", ["code", "version", "exam_type", "name", "source", "is_active"],
              [[CODE, VERSION, EXAM_TYPE, NAME, SOURCE, 1]])  # fmt: skip
    write_csv(
        out / "words.csv",
        ["language", "lemma", "lemma_norm", "phonetic", "is_active"],
        [["en", w, w, ecdict[w]["phonetic"].replace("ә", "ə")[:100], 1] for w in book if w not in demo_words],
    )
    write_csv(
        out / "senses.csv",
        ["lemma_norm", "sense_key", "part_of_speech", "definition_zh", "definition_en", "is_active"],
        [
            [s["lemma"], s["key"], s["pos"], s["zh"], en[s["lemma"]].get(POS_FAMILY.get(s["pos"]), ""), 1]
            for s in senses
        ],
    )
    write_csv(
        out / "memberships.csv",
        ["wordbook_code", "wordbook_version", "lemma_norm", "position", "source_note"],
        [[CODE, VERSION, w, i, ""] for i, w in enumerate(book, start=1)],
    )
    write_csv(
        out / "examples.csv",
        EXAMPLE_COLUMNS,
        examples,
    )
    write_csv(
        out / "relations.csv",
        ["lemma_norm_a", "lemma_norm_b", "relation_type", "source", "is_active"],
        [[a, b, t, src, 1] for (a, b, t), src in sorted(relations.items())],
    )
    with open(out / "questions.jsonl", "w", encoding="utf-8") as f:
        for q in questions:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")
    counts = defaultdict(int)
    for q in questions:
        counts[q["skill_type"]] += 1
    types = defaultdict(int)
    for _, _, t in relations:
        types[t] += 1
    print(f"词条 {len(book)}（沿用演示词条 {len(book_set & demo_words)}），新词义 {len(senses)}，例句 {len(examples)}")
    print("题目", dict(counts), "词对", dict(types))


if __name__ == "__main__":
    raw = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "raw"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "v1"
    build(raw, out)
