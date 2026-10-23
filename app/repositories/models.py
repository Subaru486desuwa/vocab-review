"""模型版本登记与推理事件留证。"""


def find_model_version(conn, model_code, version):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, kind, model_code, version, artifact_sha256, feature_schema_version, status FROM model_versions"
            " WHERE model_code = %s AND version = %s",
            (model_code, version),
        )
        return cur.fetchone()


def insert_model_version(conn, *, kind, model_code, version, artifact_sha256, feature_schema_version, metadata_json):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO model_versions (kind, model_code, version, artifact_sha256, feature_schema_version,"
            " metadata_json, status) VALUES (%s, %s, %s, %s, %s, %s, 'active')",
            (kind, model_code, version, artifact_sha256, feature_schema_version, metadata_json),
        )
        return cur.lastrowid


def insert_inference_event(
    conn,
    *,
    request_id,
    user_id,
    model_version_id,
    kind,
    source_type,
    input_json,
    output_json,
    status,
    model_time_ms,
    processing_time_ms,
    created_at,
):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO inference_events (request_id, user_id, model_version_id, kind, source_type, input_json,"
            " output_json, status, model_time_ms, processing_time_ms, created_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                request_id,
                user_id,
                model_version_id,
                kind,
                source_type,
                input_json,
                output_json,
                status,
                model_time_ms,
                processing_time_ms,
                created_at,
            ),
        )
        return cur.lastrowid
