"""词对关系（word_relations）的只读查询。"""


def partners(conn, word_ids):
    """词条的启用词对，双向展开：每行 word_id、partner_id、partner_lemma、relation_type。"""
    if not word_ids:
        return []
    ids = tuple(word_ids)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT x.word_id, x.partner_id, w.lemma AS partner_lemma, r.relation_type FROM ("
            " SELECT id, word_id_a AS word_id, word_id_b AS partner_id FROM word_relations"
            "  WHERE is_active AND word_id_a IN %s"
            " UNION ALL SELECT id, word_id_b, word_id_a FROM word_relations WHERE is_active AND word_id_b IN %s"
            ") x JOIN word_relations r ON r.id = x.id JOIN words w ON w.id = x.partner_id AND w.is_active"
            " ORDER BY x.word_id, w.lemma_norm, r.relation_type",
            (ids, ids),
        )
        return cur.fetchall()


def word_senses(conn, word_ids):
    """词条的启用词义，按词义 id。"""
    if not word_ids:
        return []
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id AS sense_id, word_id, part_of_speech, definition_zh FROM word_senses"
            " WHERE is_active AND word_id IN %s ORDER BY id",
            (tuple(word_ids),),
        )
        return cur.fetchall()
