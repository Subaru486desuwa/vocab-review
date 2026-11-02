"""练习、题目实例、作答与学习状态的读写。

作答事务的加锁顺序固定为 practice_sessions → session_items → attempts → learning_state；
需要看到其他事务已提交结果的读取一律使用锁定读。
"""

_ITEM_COLUMNS = (
    "i.id, i.position, i.question_id, i.submitted_at, q.skill_type, q.prompt, q.options_json, q.answers_json,"
    " q.grading_policy_json, q.sense_id, s.definition_zh, s.word_id, w.lemma,"
    " a.id AS attempt_id, a.normalized_answer, a.is_correct, a.error_type, a.submitted_at AS attempt_submitted_at"
)
_ITEM_JOINS = (
    " FROM session_items i JOIN questions q ON q.id = i.question_id"
    " JOIN word_senses s ON s.id = q.sense_id JOIN words w ON w.id = s.word_id"
    " LEFT JOIN attempts a ON a.session_item_id = i.id"
)


def candidate_senses(conn, wordbook_ids, skill_type):
    """目标词表中启用的词条与词义，且该题型有已发布题目；按词义去重。"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT s.id FROM wordbook_words m"
            " JOIN wordbooks b ON b.id = m.wordbook_id AND b.is_active"
            " JOIN words w ON w.id = m.word_id AND w.is_active"
            " JOIN word_senses s ON s.word_id = w.id AND s.is_active"
            " JOIN questions q ON q.sense_id = s.id AND q.skill_type = %s AND q.status = 'published'"
            " WHERE m.wordbook_id IN %s ORDER BY s.id",
            (skill_type, tuple(wordbook_ids)),
        )
        return [row["id"] for row in cur.fetchall()]


def learning_states(conn, user_id, skill_type, sense_ids):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT sense_id, seen_count, correct_streak, next_review_at FROM learning_state"
            " WHERE user_id = %s AND skill_type = %s AND sense_id IN %s",
            (user_id, skill_type, tuple(sense_ids)),
        )
        return {row["sense_id"]: row for row in cur.fetchall()}


def published_questions(conn, sense_ids, skill_type):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, sense_id FROM questions WHERE status = 'published' AND skill_type = %s AND sense_id IN %s"
            " ORDER BY id",
            (skill_type, tuple(sense_ids)),
        )
        return cur.fetchall()


def insert_session(conn, user_id, target_snapshot_json, started_at):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO practice_sessions (user_id, target_snapshot_json, status, started_at)"
            " VALUES (%s, %s, 'active', %s)",
            (user_id, target_snapshot_json, started_at),
        )
        return cur.lastrowid


def insert_items(conn, session_id, question_ids, issued_at):
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO session_items (session_id, question_id, position, issued_at) VALUES (%s, %s, %s, %s)",
            [(session_id, qid, position, issued_at) for position, qid in enumerate(question_ids, start=1)],
        )


def find_session(conn, session_id, user_id):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, user_id, target_snapshot_json, status, started_at, finished_at FROM practice_sessions"
            " WHERE id = %s AND user_id = %s",
            (session_id, user_id),
        )
        return cur.fetchone()


def session_items(conn, session_id):
    with conn.cursor() as cur:
        cur.execute(f"SELECT {_ITEM_COLUMNS}{_ITEM_JOINS} WHERE i.session_id = %s ORDER BY i.position", (session_id,))
        return cur.fetchall()


def find_item_session(conn, item_id, user_id):
    """题目实例所属练习；不属于该用户时返回 None。"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT i.session_id FROM session_items i JOIN practice_sessions p ON p.id = i.session_id"
            " WHERE i.id = %s AND p.user_id = %s",
            (item_id, user_id),
        )
        return cur.fetchone()


def lock_session(conn, session_id):
    with conn.cursor() as cur:
        cur.execute("SELECT id, user_id, status FROM practice_sessions WHERE id = %s FOR UPDATE", (session_id,))
        return cur.fetchone()


def lock_item(conn, item_id):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, session_id, question_id, submitted_at FROM session_items WHERE id = %s FOR UPDATE", (item_id,)
        )
        return cur.fetchone()


def item_with_question(conn, item_id):
    """题目版本不可变，普通读取即可。"""
    with conn.cursor() as cur:
        cur.execute(f"SELECT {_ITEM_COLUMNS}{_ITEM_JOINS} WHERE i.id = %s", (item_id,))
        return cur.fetchone()


def lock_attempt(conn, item_id):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id AS attempt_id, normalized_answer, is_correct, error_type, submitted_at AS attempt_submitted_at"
            " FROM attempts WHERE session_item_id = %s FOR UPDATE",
            (item_id,),
        )
        return cur.fetchone()


def ensure_learning_state(conn, user_id, sense_id, skill_type):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO learning_state (user_id, sense_id, skill_type) VALUES (%s, %s, %s)"
            " ON DUPLICATE KEY UPDATE id = id",
            (user_id, sense_id, skill_type),
        )


def lock_learning_state(conn, user_id, sense_id, skill_type):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, seen_count, correct_count, correct_streak, interval_stage, last_attempt_at, next_review_at"
            " FROM learning_state WHERE user_id = %s AND sense_id = %s AND skill_type = %s FOR UPDATE",
            (user_id, sense_id, skill_type),
        )
        return cur.fetchone()


def insert_attempt(
    conn,
    *,
    session_item_id,
    raw_answer_json,
    normalized_answer,
    is_correct,
    error_type,
    review_rule_version,
    submitted_at,
):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO attempts (session_item_id, raw_answer_json, normalized_answer, is_correct, error_type,"
            " review_rule_version, submitted_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                session_item_id,
                raw_answer_json,
                normalized_answer,
                is_correct,
                error_type,
                review_rule_version,
                submitted_at,
            ),
        )
        return cur.lastrowid


def update_learning_state(conn, state_id, state):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE learning_state SET seen_count = %s, correct_count = %s, correct_streak = %s, interval_stage = %s,"
            " last_attempt_at = %s, next_review_at = %s WHERE id = %s",
            (
                state["seen_count"],
                state["correct_count"],
                state["correct_streak"],
                state["interval_stage"],
                state["last_attempt_at"],
                state["next_review_at"],
                state_id,
            ),
        )


def mark_item_submitted(conn, item_id, submitted_at):
    with conn.cursor() as cur:
        cur.execute("UPDATE session_items SET submitted_at = %s WHERE id = %s", (submitted_at, item_id))


def count_unsubmitted(conn, session_id):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM session_items WHERE session_id = %s AND submitted_at IS NULL FOR SHARE",
            (session_id,),
        )
        return cur.fetchone()["n"]


def complete_session(conn, session_id, finished_at):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE practice_sessions SET status = 'completed', finished_at = %s WHERE id = %s",
            (finished_at, session_id),
        )
