"""内容包导入：先整批预检并报告行级错误，全部通过后在同一事务内写入。

格式见 docs/content-format.md。词条、词义、词表、例句按业务键新增或更新；题目按
(logical_key, version) 只增不改，新版本发布后旧版本停用，历史练习仍引用旧版本。
"""

import csv
import io
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from app.repositories import content as repo
from app.repositories import db


@dataclass(frozen=True)
class Spec:
    required: tuple
    optional: tuple = ()


SPECS = {
    "wordbooks.csv": Spec(("code", "version", "exam_type", "name", "source"), ("is_active",)),
    "words.csv": Spec(("lemma", "lemma_norm"), ("language", "phonetic", "is_active")),
    "senses.csv": Spec(("lemma_norm", "sense_key", "part_of_speech", "definition_zh"), ("definition_en", "is_active")),
    "memberships.csv": Spec(("wordbook_code", "wordbook_version", "lemma_norm", "position"), ("source_note",)),
    "examples.csv": Spec(
        ("example_key", "lemma_norm", "sense_key", "text_en", "source", "content_version"),
        ("translation_zh", "is_active"),
    ),
    "questions.jsonl": Spec(
        ("logical_key", "version", "lemma_norm", "sense_key", "skill_type", "prompt", "answers", "grading_policy"),
        ("options", "status"),
    ),
}
EXAM_TYPES = ("cet6", "postgraduate", "ielts")
CHOICE_SKILLS = ("recognition", "context")
SKILL_TYPES = (*CHOICE_SKILLS, "spelling")
_KEY = re.compile(r"[A-Za-z0-9_.-]+")


@dataclass(frozen=True)
class RowError:
    file: str
    line: int
    field: str | None
    message: str


class ImportFailed(Exception):
    def __init__(self, errors):
        super().__init__(f"预检未通过：{len(errors)} 处错误")
        self.errors = errors


@dataclass
class Row:
    file: str
    line: int
    data: dict


def normalize_lemma(lemma):
    """Unicode NFC、去首尾空白、小写、合并内部空白；显示形式另存于 lemma。"""
    return " ".join(unicodedata.normalize("NFC", lemma).strip().lower().split())


def read_directory(path):
    """读取目录中约定文件名的内容包，忽略其他文件。"""
    directory = Path(path)
    if not directory.is_dir():
        raise ImportFailed([RowError(str(path), 0, None, "目录不存在")])
    texts = {}
    for name in SPECS:
        file = directory / name
        if file.exists():
            texts[name] = file.read_bytes()
    if not texts:
        raise ImportFailed([RowError(str(path), 0, None, "目录中没有可导入的文件：" + "、".join(SPECS))])
    return texts


def import_content(conn, texts, now, dry_run=False):
    """预检并写入内容包，返回各文件的新增/更新/未变计数；dry_run 时撤销写入。

    texts 为 文件名 → 内容（str 或 UTF-8 bytes）。任何错误都使整批不写入。
    """
    with db.transaction(conn):
        batch = _Batch(conn)
        batch.parse(texts)
        batch.validate()
        if batch.errors:
            raise ImportFailed(batch.errors)
        summary = batch.write(now)
        if dry_run:
            conn.rollback()
    return summary


class _Batch:
    def __init__(self, conn):
        self.conn = conn
        self.errors = []
        self.rows = {name: [] for name in SPECS}

    def error(self, row, field, message):
        self.errors.append(RowError(row.file, row.line, field, message))

    # ---- 解析 ----

    def parse(self, texts):
        for name, content in texts.items():
            if name not in SPECS:
                self.errors.append(RowError(name, 0, None, "未知文件"))
                continue
            if isinstance(content, bytes):
                try:
                    content = content.decode("utf-8-sig")
                except UnicodeDecodeError:
                    self.errors.append(RowError(name, 0, None, "文件不是 UTF-8 编码"))
                    continue
            content = content.lstrip("﻿")
            (self._parse_jsonl if name.endswith(".jsonl") else self._parse_csv)(name, content)

    def _check_columns(self, name, line, columns, label):
        spec = SPECS[name]
        missing = [c for c in spec.required if c not in columns]
        unknown = [c for c in columns if c not in spec.required + spec.optional]
        for column in missing:
            self.errors.append(RowError(name, line, column, f"缺少{label}：{column}"))
        for column in unknown:
            self.errors.append(RowError(name, line, column, f"未知{label}：{column}"))
        return not missing and not unknown

    def _parse_csv(self, name, content):
        reader = csv.DictReader(io.StringIO(content))
        if not self._check_columns(name, 1, reader.fieldnames or [], "列"):
            return
        for record in reader:
            row = Row(name, reader.line_num, {})
            if None in record:
                self.error(row, None, "列数多于表头")
                continue
            row.data = {key: (value or "").strip() for key, value in record.items()}
            self.rows[name].append(row)

    def _parse_jsonl(self, name, content):
        for number, text in enumerate(content.splitlines(), start=1):
            if not text.strip():
                continue
            row = Row(name, number, {})
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                self.error(row, None, "不是合法 JSON")
                continue
            if not isinstance(data, dict):
                self.error(row, None, "每行必须是 JSON 对象")
                continue
            if self._check_columns(name, number, list(data), "字段"):
                row.data = data
                self.rows[name].append(row)

    # ---- 预检 ----

    def validate(self):
        conn = self.conn
        self.existing = {
            "wordbooks": repo.load_wordbooks(conn),
            "words": repo.load_words(conn),
            "senses": repo.load_senses(conn),
            "memberships": repo.load_memberships(conn),
            "examples": repo.load_examples(conn),
            "questions": repo.load_question_versions(conn),
        }
        self.known_wordbooks = set(self.existing["wordbooks"])
        self.known_words = set(self.existing["words"])
        self.known_senses = set(self.existing["senses"])
        self._validate_wordbooks()
        self._validate_words()
        self._validate_senses()
        self._validate_memberships()
        self._validate_examples()
        self._validate_questions()

    def _text(self, row, field, max_length, required=True, pattern=None):
        value = row.data.get(field)
        value = "" if value is None else value
        if not isinstance(value, str):
            self.error(row, field, f"{field} 必须是字符串")
            return ""
        if required and not value:
            self.error(row, field, f"{field} 不能为空")
        elif len(value) > max_length:
            self.error(row, field, f"{field} 超过 {max_length} 字符")
        elif value and pattern is not None and not pattern.fullmatch(value):
            self.error(row, field, f"{field} 只能包含字母、数字、点、下划线和连字符")
        return value

    def _flag(self, row, field="is_active"):
        value = row.data.get(field, "")
        if value in ("", "1"):
            return True
        if value == "0":
            return False
        self.error(row, field, f"{field} 只能为 1 或 0")
        return True

    def _unique(self, seen, key, row, field, message):
        if key in seen:
            self.error(row, field, message)
            return False
        seen.add(key)
        return True

    def _validate_wordbooks(self):
        seen = set()
        for row in self.rows["wordbooks.csv"]:
            code = self._text(row, "code", 64, pattern=_KEY)
            version = self._text(row, "version", 32, pattern=_KEY)
            exam_type = self._text(row, "exam_type", 16)
            if exam_type and exam_type not in EXAM_TYPES:
                self.error(row, "exam_type", "exam_type 只能为 " + "/".join(EXAM_TYPES))
            self._text(row, "name", 128)
            source = self._text(row, "source", 255)
            row.data["is_active"] = self._flag(row)
            key = (code, version)
            self._unique(seen, key, row, "code", f"重复键：词表 {code} {version}")
            old = self.existing["wordbooks"].get(key)
            if old is not None and (old["source"], old["exam_type"]) != (source, exam_type):
                self.error(row, "source", "同一词表版本的来源与考试类型不可修改；请发布新版本")
            self.known_wordbooks.add(key)

    def _validate_words(self):
        seen = set()
        for row in self.rows["words.csv"]:
            language = row.data.get("language") or "en"
            if language != "en":
                self.error(row, "language", "首版只支持 language=en")
            row.data["language"] = language
            lemma = self._text(row, "lemma", 100)
            lemma_norm = self._text(row, "lemma_norm", 100)
            if lemma and lemma_norm != normalize_lemma(lemma):
                self.error(row, "lemma_norm", f"lemma_norm 应为 {normalize_lemma(lemma)}")
            self._text(row, "phonetic", 100, required=False)
            row.data["is_active"] = self._flag(row)
            self._unique(seen, lemma_norm, row, "lemma_norm", f"重复键：词条 {lemma_norm}")
            self.known_words.add(lemma_norm)

    def _require_word(self, row, lemma_norm):
        if lemma_norm and lemma_norm not in self.known_words:
            self.error(row, "lemma_norm", f"词条不存在：{lemma_norm}")

    def _require_sense(self, row):
        key = (row.data.get("lemma_norm"), row.data.get("sense_key"))
        if all(isinstance(k, str) and k for k in key) and key not in self.known_senses:
            self.error(row, "sense_key", f"词义不存在：{key[0]}/{key[1]}")
        return key

    def _validate_senses(self):
        seen = set()
        for row in self.rows["senses.csv"]:
            lemma_norm = self._text(row, "lemma_norm", 100)
            self._require_word(row, lemma_norm)
            sense_key = self._text(row, "sense_key", 64, pattern=_KEY)
            self._text(row, "part_of_speech", 16)
            self._text(row, "definition_zh", 255)
            self._text(row, "definition_en", 500, required=False)
            row.data["is_active"] = self._flag(row)
            key = (lemma_norm, sense_key)
            self._unique(seen, key, row, "sense_key", f"重复键：词义 {lemma_norm}/{sense_key}")
            self.known_senses.add(key)

    def _validate_memberships(self):
        seen = set()
        for row in self.rows["memberships.csv"]:
            code = self._text(row, "wordbook_code", 64)
            version = self._text(row, "wordbook_version", 32)
            if code and version and (code, version) not in self.known_wordbooks:
                self.error(row, "wordbook_code", f"词表不存在：{code} {version}")
            lemma_norm = self._text(row, "lemma_norm", 100)
            self._require_word(row, lemma_norm)
            position = row.data.get("position", "")
            if not position.isdigit() or int(position) < 1:
                self.error(row, "position", "position 必须是正整数")
            else:
                row.data["position"] = int(position)
            self._text(row, "source_note", 255, required=False)
            key = (code, version, lemma_norm)
            self._unique(seen, key, row, "lemma_norm", f"重复关系：词表 {code} {version} 已包含 {lemma_norm}")

    def _validate_examples(self):
        seen = set()
        for row in self.rows["examples.csv"]:
            example_key = self._text(row, "example_key", 128, pattern=_KEY)
            self._text(row, "lemma_norm", 100)
            self._text(row, "sense_key", 64)
            sense = self._require_sense(row)
            text_en = self._text(row, "text_en", 1000)
            self._text(row, "translation_zh", 1000, required=False)
            self._text(row, "source", 255)
            content_version = self._text(row, "content_version", 32, pattern=_KEY)
            row.data["is_active"] = self._flag(row)
            self._unique(seen, example_key, row, "example_key", f"重复键：例句 {example_key}")
            old = self.existing["examples"].get(example_key)
            if old is None:
                continue
            old_sense = self.existing["senses"].get(sense)
            if old_sense is None or old_sense["id"] != old["sense_id"]:
                self.error(row, "sense_key", f"例句 {example_key} 已绑定其他词义")
            elif old["text_en"] != text_en and old["content_version"] == content_version:
                self.error(row, "content_version", "修改正文需要新的 content_version")

    def _validate_questions(self):
        seen = set()
        for row in self.rows["questions.jsonl"]:
            data = row.data
            logical_key = self._text(row, "logical_key", 128, pattern=_KEY)
            version = data.get("version")
            if not isinstance(version, int) or isinstance(version, bool) or version < 1:
                self.error(row, "version", "version 必须是正整数")
                version = None
            self._text(row, "lemma_norm", 100)
            self._text(row, "sense_key", 64)
            sense = self._require_sense(row)
            skill_type = data.get("skill_type")
            if skill_type not in SKILL_TYPES:
                self.error(row, "skill_type", "skill_type 只能为 " + "/".join(SKILL_TYPES))
            self._text(row, "prompt", 1000)
            status = data.setdefault("status", "published")
            if status not in ("published", "retired"):
                self.error(row, "status", "status 只能为 published 或 retired")
            if skill_type in CHOICE_SKILLS:
                self._validate_choice(row)
            elif skill_type == "spelling":
                self._validate_spelling(row)
            self._unique(seen, logical_key, row, "logical_key", f"同一批次只能包含题目 {logical_key} 的一个版本")
            if version is not None and logical_key:
                self._validate_version(row, logical_key, version, sense, skill_type)

    def _validate_choice(self, row):
        options = row.data.get("options")
        valid = (
            isinstance(options, list)
            and len(options) >= 2
            and all(
                isinstance(o, dict)
                and set(o) == {"id", "text"}
                and isinstance(o["id"], str)
                and isinstance(o["text"], str)
                and o["id"]
                and o["text"].strip()
                for o in options
            )
            and len({o["id"] for o in options}) == len(options)
        )
        if not valid:
            self.error(row, "options", "options 必须是至少两个 id 互不相同的 {id, text} 选项")
        ids = {o.get("id") for o in options if isinstance(o, dict)} if isinstance(options, list) else set()
        answers = row.data.get("answers")
        if not isinstance(answers, dict) or answers.get("option_id") not in ids:
            self.error(row, "answers", "answers.option_id 必须是选项之一")
        if row.data.get("grading_policy") != {"type": "choice"}:
            self.error(row, "grading_policy", 'grading_policy 应为 {"type": "choice"}')

    def _validate_spelling(self, row):
        if row.data.get("options") is not None:
            self.error(row, "options", "spelling 题不应有 options")
        row.data["options"] = None
        answers = row.data.get("answers")
        accepted = answers.get("accepted") if isinstance(answers, dict) else None
        if not isinstance(accepted, list) or not accepted:
            self.error(row, "answers", "answers.accepted 不能为空")
        elif not all(isinstance(a, str) and a.strip() for a in accepted):
            self.error(row, "answers", "answers.accepted 只能包含非空字符串")
        policy = row.data.get("grading_policy")
        if not (
            isinstance(policy, dict)
            and policy.get("type") == "text"
            and isinstance(policy.get("trim"), bool)
            and isinstance(policy.get("case_sensitive"), bool)
            and set(policy) == {"type", "trim", "case_sensitive"}
        ):
            self.error(
                row, "grading_policy", 'grading_policy 应为 {"type": "text", "trim": 布尔, "case_sensitive": 布尔}'
            )

    def _validate_version(self, row, logical_key, version, sense, skill_type):
        versions = self.existing["questions"].get(logical_key, [])
        old_sense = self.existing["senses"].get(sense)
        if versions and (
            old_sense is None or (versions[-1]["sense_id"], versions[-1]["skill_type"]) != (old_sense["id"], skill_type)
        ):
            self.error(row, "logical_key", f"题目 {logical_key} 已绑定其他词义或题型")
            return
        same = next((v for v in versions if v["version"] == version), None)
        if same is not None:
            if _question_content(same) != _row_content(row.data):
                self.error(row, "version", f"题目 {logical_key} v{version} 已存在且内容不同；修改请新增版本")
            return
        expected = versions[-1]["version"] + 1 if versions else 1
        if version != expected:
            self.error(row, "version", f"题目 {logical_key} 下一版本应为 {expected}")

    # ---- 写入 ----

    def write(self, now):
        summary = {name.split(".")[0]: {"inserted": 0, "updated": 0, "unchanged": 0} for name in SPECS}
        summary["questions"]["retired"] = 0
        self._write_wordbooks(summary["wordbooks"], now)
        self._write_words(summary["words"])
        self._write_senses(summary["senses"])
        self._write_memberships(summary["memberships"])
        self._write_examples(summary["examples"])
        self._write_questions(summary["questions"])
        return summary

    @staticmethod
    def _changed(old, new):
        return any(old[key] != value for key, value in new.items())

    def _write_wordbooks(self, counts, now):
        books = self.existing["wordbooks"]
        for row in self.rows["wordbooks.csv"]:
            d = row.data
            key = (d["code"], d["version"])
            old = books.get(key)
            if old is None:
                fields = {k: d[k] for k in ("code", "version", "exam_type", "name", "source", "is_active")}
                books[key] = {"id": repo.insert_wordbook(self.conn, **fields, created_at=now)}
                counts["inserted"] += 1
            elif self._changed(old, {"name": d["name"], "is_active": d["is_active"]}):
                repo.update_wordbook(self.conn, old["id"], name=d["name"], is_active=d["is_active"])
                counts["updated"] += 1
            else:
                counts["unchanged"] += 1

    def _write_words(self, counts):
        words = self.existing["words"]
        for row in self.rows["words.csv"]:
            d = row.data
            fields = {"lemma": d["lemma"], "phonetic": d.get("phonetic") or None, "is_active": d["is_active"]}
            old = words.get(d["lemma_norm"])
            if old is None:
                new_id = repo.insert_word(self.conn, language=d["language"], lemma_norm=d["lemma_norm"], **fields)
                words[d["lemma_norm"]] = {"id": new_id}
                counts["inserted"] += 1
            elif self._changed(old, fields):
                repo.update_word(self.conn, old["id"], **fields)
                counts["updated"] += 1
            else:
                counts["unchanged"] += 1

    def _write_senses(self, counts):
        senses = self.existing["senses"]
        for row in self.rows["senses.csv"]:
            d = row.data
            key = (d["lemma_norm"], d["sense_key"])
            fields = {
                "part_of_speech": d["part_of_speech"],
                "definition_zh": d["definition_zh"],
                "definition_en": d.get("definition_en") or None,
                "is_active": d["is_active"],
            }
            old = senses.get(key)
            if old is None:
                word_id = self.existing["words"][d["lemma_norm"]]["id"]
                senses[key] = {"id": repo.insert_sense(self.conn, word_id=word_id, sense_key=d["sense_key"], **fields)}
                counts["inserted"] += 1
            elif self._changed(old, fields):
                repo.update_sense(self.conn, old["id"], **fields)
                counts["updated"] += 1
            else:
                counts["unchanged"] += 1

    def _write_memberships(self, counts):
        for row in self.rows["memberships.csv"]:
            d = row.data
            ids = {
                "wordbook_id": self.existing["wordbooks"][(d["wordbook_code"], d["wordbook_version"])]["id"],
                "word_id": self.existing["words"][d["lemma_norm"]]["id"],
            }
            fields = {"position": d["position"], "source_note": d.get("source_note") or None}
            old = self.existing["memberships"].get((d["wordbook_code"], d["wordbook_version"], d["lemma_norm"]))
            if old is None:
                repo.insert_membership(self.conn, **ids, **fields)
                counts["inserted"] += 1
            elif self._changed(old, fields):
                repo.update_membership(self.conn, **ids, **fields)
                counts["updated"] += 1
            else:
                counts["unchanged"] += 1

    def _write_examples(self, counts):
        for row in self.rows["examples.csv"]:
            d = row.data
            fields = {
                "text_en": d["text_en"],
                "translation_zh": d.get("translation_zh") or None,
                "source": d["source"],
                "content_version": d["content_version"],
                "is_active": d["is_active"],
            }
            old = self.existing["examples"].get(d["example_key"])
            if old is None:
                sense_id = self.existing["senses"][(d["lemma_norm"], d["sense_key"])]["id"]
                repo.insert_example(self.conn, example_key=d["example_key"], sense_id=sense_id, **fields)
                counts["inserted"] += 1
            elif self._changed(old, fields):
                repo.update_example(self.conn, old["id"], **fields)
                counts["updated"] += 1
            else:
                counts["unchanged"] += 1

    def _write_questions(self, counts):
        for row in self.rows["questions.jsonl"]:
            d = row.data
            versions = self.existing["questions"].get(d["logical_key"], [])
            same = next((v for v in versions if v["version"] == d["version"]), None)
            if same is None:
                question_id = repo.insert_question(
                    self.conn,
                    logical_key=d["logical_key"],
                    version=d["version"],
                    sense_id=self.existing["senses"][(d["lemma_norm"], d["sense_key"])]["id"],
                    skill_type=d["skill_type"],
                    prompt=d["prompt"],
                    options_json=_dump(d["options"]),
                    answers_json=_dump(d["answers"]),
                    grading_policy_json=_dump(d["grading_policy"]),
                    status=d["status"],
                )
                counts["inserted"] += 1
                if d["status"] == "published":
                    counts["retired"] += repo.retire_other_versions(self.conn, d["logical_key"], question_id)
            elif same is versions[-1] and same["status"] != d["status"]:
                # 只有最新版本可以改状态；被取代的旧版本保持停用。
                repo.set_question_status(self.conn, same["id"], d["status"])
                counts["updated"] += 1
            else:
                counts["unchanged"] += 1


def _dump(value):
    return None if value is None else json.dumps(value, ensure_ascii=False)


def _load(value):
    return None if value is None else json.loads(value)


def _question_content(row):
    return (
        row["prompt"],
        _load(row["options_json"]),
        _load(row["answers_json"]),
        _load(row["grading_policy_json"]),
    )


def _row_content(data):
    return (data.get("prompt"), data.get("options"), data.get("answers"), data.get("grading_policy"))
