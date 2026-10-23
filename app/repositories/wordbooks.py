def _filter(exam_type):
    return ("b.is_active AND b.exam_type = %s", (exam_type,)) if exam_type else ("b.is_active", ())


def list_active(conn, user_id, exam_type, limit, offset):
    where, params = _filter(exam_type)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT b.id, b.code, b.version, b.exam_type, b.name, b.source,"
            " (SELECT COUNT(*) FROM wordbook_words m JOIN words w ON w.id = m.word_id AND w.is_active"
            "  WHERE m.wordbook_id = b.id) AS word_count,"
            " EXISTS (SELECT 1 FROM user_wordbooks u WHERE u.user_id = %s AND u.wordbook_id = b.id) AS selected"
            f" FROM wordbooks b WHERE {where} ORDER BY b.exam_type, b.code, b.version LIMIT %s OFFSET %s",
            (user_id, *params, limit, offset),
        )
        return cur.fetchall()


def count_active(conn, exam_type):
    where, params = _filter(exam_type)
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS n FROM wordbooks b WHERE {where}", params)
        return cur.fetchone()["n"]


def active_ids(conn, wordbook_ids):
    if not wordbook_ids:
        return set()
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM wordbooks WHERE is_active AND id IN %s", (tuple(wordbook_ids),))
        return {row["id"] for row in cur.fetchall()}


def selected(conn, user_id):
    """用户当前选择且仍启用的目标词表。"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT b.id, b.code, b.version, b.exam_type, b.name FROM user_wordbooks u"
            " JOIN wordbooks b ON b.id = u.wordbook_id WHERE u.user_id = %s AND b.is_active"
            " ORDER BY b.exam_type, b.code",
            (user_id,),
        )
        return cur.fetchall()


def lock_user(conn, user_id):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE id = %s FOR UPDATE", (user_id,))


def replace_selection(conn, user_id, wordbook_ids, selected_at):
    """只改目标关联；保留仍在目标中的原选择时间，作答历史不受影响。"""
    with conn.cursor() as cur:
        if wordbook_ids:
            cur.execute(
                "DELETE FROM user_wordbooks WHERE user_id = %s AND wordbook_id NOT IN %s",
                (user_id, tuple(wordbook_ids)),
            )
            cur.executemany(
                "INSERT INTO user_wordbooks (user_id, wordbook_id, selected_at) VALUES (%s, %s, %s)"
                " ON DUPLICATE KEY UPDATE selected_at = selected_at",
                [(user_id, wordbook_id, selected_at) for wordbook_id in wordbook_ids],
            )
        else:
            cur.execute("DELETE FROM user_wordbooks WHERE user_id = %s", (user_id,))
