"""复习清单、统计与重建使用的只读查询及学习状态覆盖写入。"""


def scope_senses(conn, wordbook_ids):
    """目标词表中启用的词义，按词义去重，附所属词条。"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT s.id AS sense_id, s.word_id, w.lemma, s.part_of_speech, s.definition_zh"
            " FROM wordbook_words m JOIN wordbooks b ON b.id = m.wordbook_id AND b.is_active"
            " JOIN words w ON w.id = m.word_id AND w.is_active"
            " JOIN word_senses s ON s.word_id = w.id AND s.is_active"
            " WHERE m.wordbook_id IN %s ORDER BY s.id",
            (tuple(wordbook_ids),),
        )
        return cur.fetchall()


def wordbook_words(conn, wordbook_ids):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT m.wordbook_id, m.word_id FROM wordbook_words m JOIN words w ON w.id = m.word_id AND w.is_active"
            " WHERE m.wordbook_id IN %s",
            (tuple(wordbook_ids),),
        )
        return cur.fetchall()


def published_pairs(conn, sense_ids):
    """有已发布题目的 (词义, 题型)。"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT sense_id, skill_type FROM questions WHERE status = 'published' AND sense_id IN %s",
            (tuple(sense_ids),),
        )
        return {(row["sense_id"], row["skill_type"]) for row in cur.fetchall()}


def learning_states(conn, user_id, sense_ids):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT sense_id, skill_type, seen_count, correct_count, correct_streak, interval_stage,"
            " last_attempt_at, next_review_at FROM learning_state WHERE user_id = %s AND sense_id IN %s",
            (user_id, tuple(sense_ids)),
        )
        return cur.fetchall()


def attempts_for(conn, user_id, sense_ids):
    """用户在这些词义上的作答事实，按 (submitted_at, id) 排序。"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT a.id, a.is_correct, a.submitted_at, q.sense_id, q.skill_type FROM attempts a"
            " JOIN session_items i ON i.id = a.session_item_id JOIN practice_sessions p ON p.id = i.session_id"
            " JOIN questions q ON q.id = i.question_id WHERE p.user_id = %s AND q.sense_id IN %s"
            " ORDER BY a.submitted_at, a.id",
            (user_id, tuple(sense_ids)),
        )
        return cur.fetchall()


def all_attempts(conn, user_id=None):
    """重建用：全部（或某用户的）作答事实，按 (submitted_at, id) 排序。"""
    where, params = ("WHERE p.user_id = %s", (user_id,)) if user_id is not None else ("", ())
    with conn.cursor() as cur:
        cur.execute(
            "SELECT a.id, a.is_correct, a.submitted_at, a.review_rule_version, p.user_id, q.sense_id, q.skill_type"
            " FROM attempts a JOIN session_items i ON i.id = a.session_item_id"
            " JOIN practice_sessions p ON p.id = i.session_id JOIN questions q ON q.id = i.question_id"
            f" {where} ORDER BY a.submitted_at, a.id",
            params,
        )
        return cur.fetchall()


def all_learning_states(conn, user_id=None, lock=False):
    where, params = ("WHERE user_id = %s", (user_id,)) if user_id is not None else ("", ())
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, user_id, sense_id, skill_type, seen_count, correct_count, correct_streak, interval_stage,"
            f" last_attempt_at, next_review_at FROM learning_state {where} ORDER BY id"
            + (" FOR UPDATE" if lock else ""),
            params,
        )
        return cur.fetchall()


def upsert_learning_state(conn, user_id, sense_id, skill_type, state):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO learning_state (user_id, sense_id, skill_type, seen_count, correct_count, correct_streak,"
            " interval_stage, last_attempt_at, next_review_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) AS new"
            " ON DUPLICATE KEY UPDATE seen_count = new.seen_count, correct_count = new.correct_count,"
            " correct_streak = new.correct_streak, interval_stage = new.interval_stage,"
            " last_attempt_at = new.last_attempt_at, next_review_at = new.next_review_at",
            (
                user_id,
                sense_id,
                skill_type,
                state["seen_count"],
                state["correct_count"],
                state["correct_streak"],
                state["interval_stage"],
                state["last_attempt_at"],
                state["next_review_at"],
            ),
        )
