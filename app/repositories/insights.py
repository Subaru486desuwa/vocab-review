"""学习诊断使用的只读查询。"""


def attempt_details(conn, user_id):
    """用户全部作答，附题目版本（选项、答案、判分规则）与词义，按 (submitted_at, id) 排序。"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT a.id, a.is_correct, a.error_type, a.normalized_answer, a.submitted_at,"
            " q.sense_id, q.skill_type, q.options_json, q.answers_json, q.grading_policy_json,"
            " w.lemma, s.sense_key, s.part_of_speech, s.definition_zh, s.definition_en"
            " FROM attempts a JOIN session_items i ON i.id = a.session_item_id"
            " JOIN practice_sessions p ON p.id = i.session_id JOIN questions q ON q.id = i.question_id"
            " JOIN word_senses s ON s.id = q.sense_id JOIN words w ON w.id = s.word_id"
            " WHERE p.user_id = %s ORDER BY a.submitted_at, a.id",
            (user_id,),
        )
        return cur.fetchall()


def all_senses(conn):
    """全部词义（含停用），用于把误选的选项对应回词义。"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT s.id AS sense_id, s.word_id, w.lemma, w.lemma_norm, s.sense_key, s.part_of_speech, s.definition_zh,"
            " s.definition_en FROM word_senses s JOIN words w ON w.id = s.word_id ORDER BY s.id"
        )
        return cur.fetchall()
