import io
import json
from datetime import datetime
from pathlib import Path

import pytest

from app import create_app
from app.repositories import content as content_repo
from app.repositories import db
from app.services import accounts
from app.services.content_import import ImportFailed, import_content, read_directory

pytestmark = pytest.mark.db

NOW = datetime(2026, 10, 24, 0, 0, 0)
DEMO = Path(__file__).resolve().parents[1] / "data" / "demo" / "v1"
PASSWORD = "correct horse"


def spelling(key="bank-1-spelling", version=1, prompt="银行（n.），首字母 b", accepted=("bank",), sense="1"):
    return {
        "logical_key": key,
        "version": version,
        "lemma_norm": "bank",
        "sense_key": sense,
        "skill_type": "spelling",
        "prompt": prompt,
        "options": None,
        "answers": {"accepted": list(accepted)},
        "grading_policy": {"type": "text", "trim": True, "case_sensitive": False},
    }


def mini_pack(questions=None, **overrides):
    pack = {
        "wordbooks.csv": "code,version,exam_type,name,source\nmini,v1,cet6,迷你词表,测试来源\n",
        "words.csv": "language,lemma,lemma_norm\nen,Bank,bank\n",
        "senses.csv": "lemma_norm,sense_key,part_of_speech,definition_zh\nbank,1,n.,银行\n",
        "memberships.csv": "wordbook_code,wordbook_version,lemma_norm,position\nmini,v1,bank,1\n",
        "examples.csv": "example_key,lemma_norm,sense_key,text_en,source,content_version\n"
        "bank-1-1,bank,1,I went to the bank.,测试来源,c1\n",
        "questions.jsonl": "".join(json.dumps(q, ensure_ascii=False) + "\n" for q in (questions or [spelling()])),
    }
    pack.update(overrides)
    return {name: text for name, text in pack.items() if text is not None}


def count(conn, table, where="1=1", params=()):
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS n FROM {table} WHERE {where}", params)
        return cur.fetchone()["n"]


def messages(exc_info):
    return [(e.file, e.line, e.message) for e in exc_info.value.errors]


def test_demo_pack_imports_and_reimport_is_idempotent(db_conn):
    first = import_content(db_conn, read_directory(DEMO), NOW)
    assert {name: s["inserted"] for name, s in first.items()} == {
        "wordbooks": 3, "words": 70, "senses": 79, "memberships": 90, "examples": 158, "questions": 237,
        "relations": 0,
    }  # fmt: skip
    assert count(db_conn, "questions", "status = 'published'") == 237
    second = import_content(db_conn, read_directory(DEMO), NOW)
    assert all(s["inserted"] == 0 and s["updated"] == 0 for s in second.values())
    assert count(db_conn, "words") == 70


def test_demo_v2_adds_question_versions_over_v1(db_conn):
    import_content(db_conn, read_directory(DEMO), NOW)
    v1_questions = {q["id"] for q in _questions(db_conn)}
    summary = import_content(db_conn, read_directory(DEMO.parent / "v2"), NOW)
    lines = (DEMO.parent / "v2" / "questions.jsonl").read_text(encoding="utf-8").splitlines()
    bumped = sum(1 for line in lines if '"version": 2' in line)
    assert summary["questions"] == {"inserted": bumped, "updated": 0, "unchanged": 237 - bumped, "retired": bumped}
    assert (summary["senses"]["updated"], summary["examples"]["updated"]) == (1, 13)
    assert count(db_conn, "questions", "status = 'published'") == 237
    assert count(db_conn, "questions", "status = 'retired'") == bumped
    assert v1_questions <= {q["id"] for q in _questions(db_conn)}  # 旧版本保留，历史练习仍可解释


def test_demo_v3_only_adds_content_over_v2(db_conn):
    for pack in ("v1", "v2"):
        import_content(db_conn, read_directory(DEMO.parent / pack), NOW)
    published = count(db_conn, "questions", "status = 'published'")
    summary = import_content(db_conn, read_directory(DEMO.parent / "v3"), NOW)
    assert {name: (s["inserted"], s["updated"]) for name, s in summary.items()} == {
        "wordbooks": (0, 0), "words": (130, 0), "senses": (136, 0), "memberships": (150, 0),
        "examples": (272, 0), "questions": (408, 0), "relations": (0, 0),
    }  # fmt: skip
    assert summary["questions"]["retired"] == 0
    assert count(db_conn, "questions", "status = 'published'") == published + 408 == 645
    again = import_content(db_conn, read_directory(DEMO.parent / "v3"), NOW)
    assert all(s["inserted"] == 0 and s["updated"] == 0 for s in again.values())


def test_dry_run_reports_without_writing(db_conn):
    summary = import_content(db_conn, mini_pack(), NOW, dry_run=True)
    assert summary["words"]["inserted"] == 1
    assert count(db_conn, "words") == 0 and count(db_conn, "wordbooks") == 0


# T12：行级错误，正式数据无部分污染


def test_row_errors_are_reported_and_nothing_is_written(db_conn):
    pack = mini_pack(
        questions=[
            spelling(),
            spelling(key="bank-9-spelling", sense="9"),
            spelling(key="bank-1-empty", accepted=()),
            {**spelling(key="bank-1-choice"), "skill_type": "recognition", "options": [{"id": "a", "text": "银行"}],
             "answers": {"option_id": "z"}, "grading_policy": {"type": "choice"}},
        ],
        **{
            "words.csv": "language,lemma,lemma_norm\nen,Bank,bank\nen,River,river\n",
            "memberships.csv": "wordbook_code,wordbook_version,lemma_norm,position\nmini,v1,bank,1\nmini,v1,bank,2\n",
        },
    )  # fmt: skip
    with pytest.raises(ImportFailed) as exc_info:
        import_content(db_conn, pack, NOW)
    found = messages(exc_info)
    assert ("memberships.csv", 3, "重复关系：词表 mini v1 已包含 bank") in found
    assert ("questions.jsonl", 2, "词义不存在：bank/9") in found
    assert ("questions.jsonl", 3, "answers.accepted 不能为空") in found
    assert ("questions.jsonl", 4, "answers.option_id 必须是选项之一") in found
    assert count(db_conn, "words") == 0 and count(db_conn, "questions") == 0


def test_header_problems_are_reported(db_conn):
    pack = mini_pack(**{"senses.csv": "lemma_norm,part_of_speech,definition_zh,colour\nbank,n.,银行,red\n"})
    with pytest.raises(ImportFailed) as exc_info:
        import_content(db_conn, pack, NOW)
    found = messages(exc_info)
    assert ("senses.csv", 1, "缺少列：sense_key") in found
    assert ("senses.csv", 1, "未知列：colour") in found


def test_lemma_norm_must_match_normalized_lemma(db_conn):
    pack = mini_pack(**{"words.csv": "language,lemma,lemma_norm\nen,Bank,banks\n"})
    with pytest.raises(ImportFailed) as exc_info:
        import_content(db_conn, pack, NOW)
    assert ("words.csv", 2, "lemma_norm 应为 bank") in messages(exc_info)


def test_dangling_reference_to_unknown_word_is_reported(db_conn):
    pack = mini_pack(
        **{"senses.csv": "lemma_norm,sense_key,part_of_speech,definition_zh\nbank,1,n.,银行\nriver,1,n.,河\n"}
    )
    with pytest.raises(ImportFailed) as exc_info:
        import_content(db_conn, pack, NOW)
    assert ("senses.csv", 3, "词条不存在：river") in messages(exc_info)


def test_write_failure_rolls_back_whole_batch(db_conn, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("写入中断")

    monkeypatch.setattr(content_repo, "insert_question", broken)
    with pytest.raises(RuntimeError, match="写入中断"):
        import_content(db_conn, mini_pack(), NOW)
    assert count(db_conn, "words") == 0 and count(db_conn, "examples") == 0


# 题目版本与停用（T10、T11 的数据层）


def _issue_question_to_learner(conn, question_id):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (username, username_norm, password_hash, created_at) VALUES ('l', 'l', 'x', %s)", (NOW,)
        )
        cur.execute(
            "INSERT INTO practice_sessions (user_id, target_snapshot_json, started_at) VALUES (%s, '{}', %s)",
            (cur.lastrowid, NOW),
        )
        cur.execute(
            "INSERT INTO session_items (session_id, question_id, position, issued_at) VALUES (%s, %s, 1, %s)",
            (cur.lastrowid, question_id, NOW),
        )
    conn.commit()


def _questions(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id, version, prompt, status FROM questions ORDER BY version")
        return cur.fetchall()


def test_new_question_version_retires_old_one_and_keeps_history(db_conn):
    import_content(db_conn, mini_pack(), NOW)
    v1 = _questions(db_conn)[0]
    _issue_question_to_learner(db_conn, v1["id"])
    summary = import_content(db_conn, mini_pack(questions=[spelling(version=2, prompt="银行（n.）")]), NOW)
    assert summary["questions"] == {"inserted": 1, "updated": 0, "unchanged": 0, "retired": 1}
    old, new = _questions(db_conn)
    assert (old["id"], old["prompt"], old["status"]) == (v1["id"], v1["prompt"], "retired")
    assert (new["version"], new["status"]) == (2, "published")
    assert count(db_conn, "session_items", "question_id = %s", (v1["id"],)) == 1


def test_published_question_cannot_change_in_place(db_conn):
    import_content(db_conn, mini_pack(), NOW)
    with pytest.raises(ImportFailed) as exc_info:
        import_content(db_conn, mini_pack(questions=[spelling(prompt="改过的题干")]), NOW)
    assert ("questions.jsonl", 1, "题目 bank-1-spelling v1 已存在且内容不同；修改请新增版本") in messages(exc_info)


def test_question_versions_must_be_consecutive(db_conn):
    import_content(db_conn, mini_pack(), NOW)
    with pytest.raises(ImportFailed) as exc_info:
        import_content(db_conn, mini_pack(questions=[spelling(version=3)]), NOW)
    assert ("questions.jsonl", 1, "题目 bank-1-spelling 下一版本应为 2") in messages(exc_info)


def test_deactivated_content_is_kept(db_conn):
    import_content(db_conn, mini_pack(), NOW)
    pack = mini_pack(
        **{
            "words.csv": "language,lemma,lemma_norm,is_active\nen,Bank,bank,0\n",
            "examples.csv": "example_key,lemma_norm,sense_key,text_en,source,content_version,is_active\n"
            "bank-1-1,bank,1,I went to the bank.,测试来源,c1,0\n",
        }
    )
    summary = import_content(db_conn, pack, NOW)
    assert summary["words"]["updated"] == 1 and summary["examples"]["updated"] == 1
    assert count(db_conn, "words", "is_active = FALSE") == 1
    assert count(db_conn, "examples", "is_active = FALSE") == 1


def test_example_text_change_requires_new_content_version(db_conn):
    import_content(db_conn, mini_pack(), NOW)
    changed = (
        "example_key,lemma_norm,sense_key,text_en,source,content_version\n"
        "bank-1-1,bank,1,She works at a bank.,测试来源,"
    )
    with pytest.raises(ImportFailed) as exc_info:
        import_content(db_conn, mini_pack(**{"examples.csv": changed + "c1\n"}), NOW)
    assert ("examples.csv", 2, "修改正文需要新的 content_version") in messages(exc_info)
    assert import_content(db_conn, mini_pack(**{"examples.csv": changed + "c2\n"}), NOW)["examples"]["updated"] == 1


def test_wordbook_source_cannot_change_within_a_version(db_conn):
    import_content(db_conn, mini_pack(), NOW)
    pack = mini_pack(**{"wordbooks.csv": "code,version,exam_type,name,source\nmini,v1,cet6,迷你词表,另一个来源\n"})
    with pytest.raises(ImportFailed) as exc_info:
        import_content(db_conn, pack, NOW)
    assert ("wordbooks.csv", 2, "同一词表版本的来源与考试类型不可修改；请发布新版本") in messages(exc_info)


# 命令行


def _write_pack(directory, pack):
    for name, text in pack.items():
        (directory / name).write_text(text, encoding="utf-8")
    return directory


def test_import_command_reports_summary_and_errors(db_app, tmp_path):
    runner = db_app.test_cli_runner()
    ok = runner.invoke(args=["import-content", str(_write_pack(tmp_path, mini_pack())), "--dry-run"])
    assert ok.exit_code == 0, ok.output
    assert "预检通过，未写入" in ok.output and "words：新增 1" in ok.output
    ok = runner.invoke(args=["import-content", str(tmp_path)])
    assert ok.exit_code == 0 and "已提交" in ok.output
    (tmp_path / "bad").mkdir()
    bad = _write_pack(tmp_path / "bad", mini_pack(questions=[spelling(sense="9")]))
    failed = runner.invoke(args=["import-content", str(bad)])
    assert failed.exit_code == 1
    assert "questions.jsonl:1 词义不存在：bank/9" in failed.output


def test_seed_demo_user(db_app, db_config, monkeypatch):
    runner = db_app.test_cli_runner()
    monkeypatch.delenv("DEMO_USER_PASSWORD", raising=False)
    assert runner.invoke(args=["seed-demo-user"]).exit_code != 0
    monkeypatch.setenv("DEMO_USER_PASSWORD", PASSWORD)
    first = runner.invoke(args=["seed-demo-user", "--username", "demo"])
    assert first.exit_code == 0 and "已创建" in first.output
    again = runner.invoke(args=["seed-demo-user", "--username", "demo"])
    assert again.exit_code == 0 and "已存在" in again.output
    conn = db.connect(db_config)
    assert count(conn, "users", "username_norm = 'demo' AND role = 'learner'") == 1
    conn.close()


# 管理接口（T03 的导入 403）


def _client_as(db_config, role):
    app = create_app({"TESTING": True, "SECRET_KEY": "t", "WTF_CSRF_ENABLED": False, **db_config})
    client = app.test_client()
    if role:
        with app.app_context(), db.transaction() as conn:
            accounts.register(conn, role, PASSWORD, NOW, role=role)
        client.post("/auth/login", data={"username": role, "password": PASSWORD})
    return client


def _upload(pack, **fields):
    data = {name.rsplit(".", 1)[0]: (io.BytesIO(text.encode()), name) for name, text in pack.items()}
    return {**data, **fields}


def test_admin_import_requires_login_and_admin_role(db_config, migrated_db, db_conn):
    assert _client_as(db_config, None).post("/api/v1/admin/import", data=_upload(mini_pack())).status_code == 401
    learner = _client_as(db_config, "learner")
    response = learner.post("/api/v1/admin/import", data=_upload(mini_pack()))
    assert response.status_code == 403 and response.get_json()["error"]["code"] == "FORBIDDEN"
    assert count(db_conn, "words") == 0


def test_admin_import_dry_run_commit_and_row_errors(db_config, migrated_db, db_conn):
    admin = _client_as(db_config, "admin")
    dry = admin.post("/api/v1/admin/import", data=_upload(mini_pack(), dry_run="1"))
    assert dry.status_code == 200 and dry.get_json()["data"]["dry_run"] is True
    assert count(db_conn, "words") == 0
    done = admin.post("/api/v1/admin/import", data=_upload(mini_pack()))
    assert done.status_code == 200 and done.get_json()["data"]["summary"]["words"]["inserted"] == 1
    bad = admin.post("/api/v1/admin/import", data=_upload(mini_pack(questions=[spelling(sense="9")])))
    body = bad.get_json()
    assert bad.status_code == 422 and body["error"]["code"] == "IMPORT_INVALID"
    assert {"file": "questions.jsonl", "line": 1, "field": "sense_key", "message": "词义不存在：bank/9"} in body[
        "error"
    ]["rows"]
    unknown = admin.post("/api/v1/admin/import", data={"notes": (io.BytesIO(b"x"), "notes.csv")})
    assert unknown.status_code == 400
