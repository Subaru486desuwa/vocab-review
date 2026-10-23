_COLUMNS = "id, username, username_norm, password_hash, role, is_active, display_timezone"


def find_by_username_norm(conn, username_norm):
    with conn.cursor() as cur:
        cur.execute(f"SELECT {_COLUMNS} FROM users WHERE username_norm = %s", (username_norm,))
        return cur.fetchone()


def find_by_id(conn, user_id):
    with conn.cursor() as cur:
        cur.execute(f"SELECT {_COLUMNS} FROM users WHERE id = %s", (user_id,))
        return cur.fetchone()


def insert(conn, *, username, username_norm, password_hash, role, created_at):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (username, username_norm, password_hash, role, created_at) VALUES (%s, %s, %s, %s, %s)",
            (username, username_norm, password_hash, role, created_at),
        )
        return cur.lastrowid
