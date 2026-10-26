"""证据索引与报告数字的回归检查：证据重跑后格式与引用仍一致。"""

import csv
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "docs" / "reports"))

import build_reports  # noqa: E402

COLUMNS = ["file", "requirement", "command", "executed_at_utc", "notes"]
STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[.\d]*)?(?:Z|[+-]\d{2}:\d{2})|未记录.*")


def _index(directory):
    path = ROOT / "evidence" / directory / "index.csv"
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))


def test_every_evidence_index_has_five_columns():
    for path in sorted((ROOT / "evidence").glob("*/index.csv")):
        rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8"))))
        assert rows and rows[0] == COLUMNS, path
        for number, row in enumerate(rows[1:], start=2):
            assert len(row) == 5, (path.name, number, len(row))
            assert row[3] == "" or STAMP.fullmatch(row[3]), (path.name, number, row[3])


def test_index_lists_every_evidence_file_that_reports_read():
    """报告读到的证据文件必须在 index.csv 登记，避免刷新证据后忘记登记。"""
    names = {
        "exp02": {"insights-http.txt", "review-path.txt", "today-http.txt", "daily-http.txt"},
        "exp03": {"data_manifest.json", "metrics.json", "latency.json", "inference-events.txt", "consistency.txt"},
        "exp04": {"retrieval-metrics.json", "index_manifest.json", "latency.json", "lab-http.txt"},
    }
    for directory, used in names.items():
        listed = {row["file"] for row in _index(directory)}
        assert used <= listed, (directory, sorted(used - listed))


def test_insights_evidence_is_self_consistent():
    data = build_reports.insights_evidence()
    text = (ROOT / "evidence" / "exp02" / "insights-http.txt").read_text(encoding="utf-8")
    match = re.search(r"接口 (\{.*?\}) \| 数据库 作答 答错：(\d+)\s+(\d+)", text)
    assert match, "缺少与数据库对照的行"
    assert json.loads(match.group(1)) == data["attempts"], "接口数字与解析结果不一致"
    assert str(data["attempts"]["count"]) == match.group(2).strip()
    assert str(data["attempts"]["wrong"]) == match.group(3).strip()
    assert len(data["semantic"]) == len(re.findall(r"语义组 \[", text))
    assert [name for name, *_ in data["groups"]] == ["薄弱", "一般", "较稳"]
    before, after = data["read_only"]
    assert before.split() == after.split(), "只读核对前后应一致"
