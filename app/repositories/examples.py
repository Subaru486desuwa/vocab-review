def active_examples(conn):
    """启用的例句及其目标词义；词条或词义停用的例句不参与检索。"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT e.id, e.example_key, e.content_version, e.text_en, e.translation_zh, e.sense_id, w.id AS word_id,"
            " w.lemma, s.sense_key, s.part_of_speech, s.definition_zh FROM examples e"
            " JOIN word_senses s ON s.id = e.sense_id AND s.is_active JOIN words w ON w.id = s.word_id AND w.is_active"
            " WHERE e.is_active ORDER BY e.id"
        )
        return cur.fetchall()


def words_in_wordbook(conn, wordbook_id):
    """启用词表中的词条 id；词表不存在或停用时返回 None。"""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM wordbooks WHERE id = %s AND is_active", (wordbook_id,))
        if cur.fetchone() is None:
            return None
        cur.execute("SELECT word_id FROM wordbook_words WHERE wordbook_id = %s", (wordbook_id,))
        return {row["word_id"] for row in cur.fetchall()}
