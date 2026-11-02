"""词表、词条、词义、例句、题目版本与词对关系的读写；提交与回滚由调用方负责。"""


def _all(conn, sql, params=()):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def _execute(conn, sql, params):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.lastrowid


def load_wordbooks(conn):
    rows = _all(conn, "SELECT id, code, version, exam_type, name, source, is_active FROM wordbooks")
    return {(r["code"], r["version"]): r for r in rows}


def load_words(conn):
    rows = _all(conn, "SELECT id, language, lemma, lemma_norm, phonetic, is_active FROM words")
    return {r["lemma_norm"]: r for r in rows}


def load_senses(conn):
    rows = _all(
        conn,
        "SELECT s.id, s.word_id, w.lemma_norm, s.sense_key, s.part_of_speech, s.definition_zh, s.definition_en,"
        " s.is_active FROM word_senses s JOIN words w ON w.id = s.word_id",
    )
    return {(r["lemma_norm"], r["sense_key"]): r for r in rows}


def load_memberships(conn):
    rows = _all(
        conn,
        "SELECT b.code, b.version, w.lemma_norm, m.position, m.source_note FROM wordbook_words m"
        " JOIN wordbooks b ON b.id = m.wordbook_id JOIN words w ON w.id = m.word_id",
    )
    return {(r["code"], r["version"], r["lemma_norm"]): r for r in rows}


def load_examples(conn):
    rows = _all(
        conn,
        "SELECT e.id, e.example_key, e.sense_id, e.text_en, e.translation_zh, e.source, e.content_version,"
        " e.is_active FROM examples e",
    )
    return {r["example_key"]: r for r in rows}


def load_question_versions(conn):
    """logical_key → 按版本升序的全部版本。"""
    rows = _all(
        conn,
        "SELECT id, logical_key, version, sense_id, skill_type, prompt, options_json, answers_json,"
        " grading_policy_json, status FROM questions ORDER BY logical_key, version",
    )
    versions = {}
    for r in rows:
        versions.setdefault(r["logical_key"], []).append(r)
    return versions


def insert_wordbook(conn, *, code, version, exam_type, name, source, is_active, created_at):
    return _execute(
        conn,
        "INSERT INTO wordbooks (code, version, exam_type, name, source, is_active, created_at)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (code, version, exam_type, name, source, is_active, created_at),
    )


def update_wordbook(conn, wordbook_id, *, name, is_active):
    _execute(conn, "UPDATE wordbooks SET name = %s, is_active = %s WHERE id = %s", (name, is_active, wordbook_id))


def insert_word(conn, *, language, lemma, lemma_norm, phonetic, is_active):
    return _execute(
        conn,
        "INSERT INTO words (language, lemma, lemma_norm, phonetic, is_active) VALUES (%s, %s, %s, %s, %s)",
        (language, lemma, lemma_norm, phonetic, is_active),
    )


def update_word(conn, word_id, *, lemma, phonetic, is_active):
    _execute(
        conn,
        "UPDATE words SET lemma = %s, phonetic = %s, is_active = %s WHERE id = %s",
        (lemma, phonetic, is_active, word_id),
    )


def insert_sense(conn, *, word_id, sense_key, part_of_speech, definition_zh, definition_en, is_active):
    return _execute(
        conn,
        "INSERT INTO word_senses (word_id, sense_key, part_of_speech, definition_zh, definition_en, is_active)"
        " VALUES (%s, %s, %s, %s, %s, %s)",
        (word_id, sense_key, part_of_speech, definition_zh, definition_en, is_active),
    )


def update_sense(conn, sense_id, *, part_of_speech, definition_zh, definition_en, is_active):
    _execute(
        conn,
        "UPDATE word_senses SET part_of_speech = %s, definition_zh = %s, definition_en = %s, is_active = %s"
        " WHERE id = %s",
        (part_of_speech, definition_zh, definition_en, is_active, sense_id),
    )


def insert_membership(conn, *, wordbook_id, word_id, position, source_note):
    _execute(
        conn,
        "INSERT INTO wordbook_words (wordbook_id, word_id, position, source_note) VALUES (%s, %s, %s, %s)",
        (wordbook_id, word_id, position, source_note),
    )


def update_membership(conn, *, wordbook_id, word_id, position, source_note):
    _execute(
        conn,
        "UPDATE wordbook_words SET position = %s, source_note = %s WHERE wordbook_id = %s AND word_id = %s",
        (position, source_note, wordbook_id, word_id),
    )


def insert_example(conn, *, example_key, sense_id, text_en, translation_zh, source, content_version, is_active):
    return _execute(
        conn,
        "INSERT INTO examples (example_key, sense_id, text_en, translation_zh, source, content_version, is_active)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (example_key, sense_id, text_en, translation_zh, source, content_version, is_active),
    )


def update_example(conn, example_id, *, text_en, translation_zh, source, content_version, is_active):
    _execute(
        conn,
        "UPDATE examples SET text_en = %s, translation_zh = %s, source = %s, content_version = %s, is_active = %s"
        " WHERE id = %s",
        (text_en, translation_zh, source, content_version, is_active, example_id),
    )


def insert_question(
    conn, *, logical_key, version, sense_id, skill_type, prompt, options_json, answers_json, grading_policy_json, status
):
    return _execute(
        conn,
        "INSERT INTO questions (logical_key, version, sense_id, skill_type, prompt, options_json, answers_json,"
        " grading_policy_json, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (logical_key, version, sense_id, skill_type, prompt, options_json, answers_json, grading_policy_json, status),
    )


def set_question_status(conn, question_id, status):
    _execute(conn, "UPDATE questions SET status = %s WHERE id = %s", (status, question_id))


def retire_other_versions(conn, logical_key, keep_id):
    """停用同一题目的其他版本，返回受影响行数；历史练习仍引用原版本。"""
    with conn.cursor() as cur:
        return cur.execute(
            "UPDATE questions SET status = 'retired' WHERE logical_key = %s AND id <> %s AND status <> 'retired'",
            (logical_key, keep_id),
        )


def load_relations(conn):
    rows = _all(conn, "SELECT id, word_id_a, word_id_b, relation_type, source, is_active FROM word_relations")
    return {(r["word_id_a"], r["word_id_b"], r["relation_type"]): r for r in rows}


def insert_relation(conn, *, word_id_a, word_id_b, relation_type, source, is_active):
    _execute(
        conn,
        "INSERT INTO word_relations (word_id_a, word_id_b, relation_type, source, is_active)"
        " VALUES (%s, %s, %s, %s, %s)",
        (word_id_a, word_id_b, relation_type, source, is_active),
    )


def update_relation(conn, relation_id, *, source, is_active):
    _execute(
        conn, "UPDATE word_relations SET source = %s, is_active = %s WHERE id = %s", (source, is_active, relation_id)
    )
