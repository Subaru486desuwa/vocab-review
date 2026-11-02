from datetime import datetime

import pymysql
import pytest

from app.repositories import migrations

NOW = datetime(2026, 10, 24, 0, 0, 0)
INITIAL_TABLES = {
    "users", "wordbooks", "words", "word_senses", "wordbook_words", "user_wordbooks", "examples",
    "questions", "practice_sessions", "session_items", "attempts", "learning_state",
    "model_versions", "inference_events",
}  # fmt: skip
# 0003 追加词对关系表（ADR 0004）。
BUSINESS_TABLES = INITIAL_TABLES | {"word_relations"}


def test_split_statements_ignores_comment_lines_and_blank_tail():
    sql = "-- 说明; 不是语句\nCREATE TABLE a (id INT);\n\nCREATE TABLE b (id INT);\n"
    assert migrations.split_statements(sql) == ["CREATE TABLE a (id INT)", "CREATE TABLE b (id INT);"]


def test_initial_migration_creates_each_business_table_once():
    sql = (migrations.MIGRATIONS_DIR / "0001_initial_schema.sql").read_text(encoding="utf-8")
    statements = migrations.split_statements(sql)
    assert len(statements) == len(INITIAL_TABLES)
    assert {s.split()[2] for s in statements} == INITIAL_TABLES


@pytest.mark.db
def test_fresh_database_gets_all_tables(migrated_db, db_conn, table_names):
    assert migrated_db == [p.stem for p in sorted(migrations.MIGRATIONS_DIR.glob("*.sql"))]
    assert migrated_db[:2] == ["0001_initial_schema", "0002_example_key"]
    assert set(table_names(db_conn)) == BUSINESS_TABLES | {"schema_migrations"}


@pytest.mark.db
def test_upgrade_is_idempotent(db_conn):
    assert migrations.pending(db_conn) == []
    assert migrations.upgrade(db_conn, NOW) == []


@pytest.mark.db
def test_username_norm_is_unique(db_conn):
    insert = "INSERT INTO users (username, username_norm, password_hash, created_at) VALUES (%s, %s, 'x', %s)"
    with db_conn.cursor() as cur:
        cur.execute(insert, ("Alice", "alice", NOW))
        with pytest.raises(pymysql.err.IntegrityError):
            cur.execute(insert, ("ALICE", "alice", NOW))


@pytest.mark.db
def test_lemma_norm_distinguishes_accents(db_conn):
    with db_conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO words (lemma, lemma_norm) VALUES (%s, %s)", [("resume", "resume"), ("résumé", "résumé")]
        )
        cur.execute("SELECT COUNT(*) AS n FROM words")
        assert cur.fetchone()["n"] == 2


@pytest.mark.db
@pytest.mark.parametrize(
    ("column", "value"),
    [("role", "root"), ("display_timezone", None)],
)
def test_users_reject_invalid_values(db_conn, column, value):
    with db_conn.cursor() as cur, pytest.raises((pymysql.err.OperationalError, pymysql.err.IntegrityError)):
        cur.execute(
            f"INSERT INTO users (username, username_norm, password_hash, created_at, {column})"
            " VALUES ('bob', 'bob', 'x', %s, %s)",
            (NOW, value),
        )


@pytest.mark.db
def test_learning_state_counts_are_checked(db_conn):
    with db_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (username, username_norm, password_hash, created_at) VALUES ('c', 'c', 'x', %s)",
            (NOW,),
        )
        user_id = cur.lastrowid
        cur.execute("INSERT INTO words (lemma, lemma_norm) VALUES ('bank', 'bank')")
        cur.execute(
            "INSERT INTO word_senses (word_id, sense_key, part_of_speech, definition_zh)"
            " VALUES (%s, 'n1', 'n.', '银行')",
            (cur.lastrowid,),
        )
        sense_id = cur.lastrowid
        with pytest.raises(pymysql.err.OperationalError):
            cur.execute(
                "INSERT INTO learning_state (user_id, sense_id, skill_type, seen_count, correct_count)"
                " VALUES (%s, %s, 'spelling', 1, 2)",
                (user_id, sense_id),
            )
