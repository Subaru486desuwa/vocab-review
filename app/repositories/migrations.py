import re
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "sql" / "migrations"
_NAME = re.compile(r"^\d{4}_[a-z0-9_]+\.sql$")


def split_statements(sql):
    """按行尾分号切分；迁移文件只写普通 DDL/DML，不含存储过程或字符串内分号。"""
    lines = [line for line in sql.splitlines() if not line.lstrip().startswith("--")]
    return [stmt.strip() for stmt in "\n".join(lines).split(";\n") if stmt.strip().rstrip(";")]


def pending(conn, migrations_dir=MIGRATIONS_DIR):
    files = sorted(p for p in Path(migrations_dir).iterdir() if _NAME.match(p.name))
    applied = _applied_versions(conn)
    return [p for p in files if p.stem not in applied]


def upgrade(conn, now, migrations_dir=MIGRATIONS_DIR):
    """按编号执行未应用的迁移，返回本次执行的版本。

    MySQL DDL 会隐式提交，迁移中途失败时已执行的语句不会回滚，需要修正后手动清理目标库。
    """
    _ensure_table(conn)
    done = []
    for path in pending(conn, migrations_dir):
        with conn.cursor() as cur:
            for stmt in split_statements(path.read_text(encoding="utf-8")):
                cur.execute(stmt.rstrip(";"))
            cur.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (%s, %s)",
                (path.stem, now),
            )
        conn.commit()
        done.append(path.stem)
    return done


def _ensure_table(conn):
    with conn.cursor() as cur:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version VARCHAR(128) NOT NULL PRIMARY KEY,"
            " applied_at DATETIME(6) NOT NULL"
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci"
        )
    conn.commit()


def _applied_versions(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM information_schema.tables"
            " WHERE table_schema = DATABASE() AND table_name = 'schema_migrations'"
        )
        if not cur.fetchone()["n"]:
            return set()
        cur.execute("SELECT version FROM schema_migrations")
        return {row["version"] for row in cur.fetchall()}
