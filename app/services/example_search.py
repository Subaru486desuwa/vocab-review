"""实验四：英语语境例句检索。只使用本地已登记的编码器与校验通过的索引，每个进程加载一次。

每次检索都核对当前启用例句与索引的语料指纹；例句变化后拒绝旧索引，直到重建。
"""

import json
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from app.repositories import db
from app.repositories import examples as examples_repo
from app.repositories import models as model_repo

MAX_TEXT_LENGTH = 1000
MAX_TOP_K = 10
MODEL_CODE = "all-MiniLM-L6-v2"
_NON_ENGLISH = re.compile(r"[぀-ヿ㐀-鿿가-힯]")
_cache = {}
_lock = threading.Lock()


class SearchUnavailable(Exception):
    pass


class InvalidQuery(Exception):
    def __init__(self, fields):
        super().__init__("参数校验失败")
        self.fields = fields


@dataclass
class Loaded:
    model: object
    encoder_manifest: dict
    vectors: object
    ids: list
    index_manifest: dict
    index_manifest_text: str
    model_version_id: int


def reset_cache():
    with _lock:
        _cache.clear()


def _modules():
    try:
        from ml import example_index
    except ImportError as exc:
        raise SearchUnavailable("未安装模型依赖（构建镜像时 WITH_DL=1）") from exc
    return example_index


def get(conn, dl_dir):
    example_index = _modules()
    key = str(Path(dl_dir).resolve())
    manifest_path = Path(dl_dir) / example_index.INDEX_DIR / example_index.INDEX_MANIFEST
    with _lock:
        try:
            current_text = manifest_path.read_text(encoding="utf-8") if manifest_path.is_file() else None
            cached = _cache.get(key)
            if cached is not None and cached.index_manifest_text == current_text:
                return cached
            if cached is not None:
                model, encoder = cached.model, cached.encoder_manifest
            else:
                model, encoder = example_index.load_encoder(dl_dir)
            vectors, ids, index_manifest = example_index.load_index(dl_dir, encoder)
        except example_index.IndexUnavailable as exc:
            raise SearchUnavailable(str(exc)) from exc
        with db.transaction(conn):
            row = model_repo.find_model_version(conn, MODEL_CODE, encoder["revision"])
        if (
            row is None
            or row["status"] != "active"
            or row["kind"] != "dl"
            or (row["artifact_sha256"] != encoder["files"][example_index.WEIGHTS]["sha256"])
        ):
            raise SearchUnavailable("编码器未登记或登记信息与权重不符（flask build-example-index）")
        loaded = Loaded(model, encoder, vectors, ids, index_manifest, current_text, row["id"])
        _cache[key] = loaded
        return loaded


def validate(text, top_k, wordbook_id):
    fields = {}
    if not isinstance(text, str) or not text.strip():
        fields["text"] = "text 必须是非空英语文本"
    elif len(text) > MAX_TEXT_LENGTH:
        fields["text"] = f"text 超过 {MAX_TEXT_LENGTH} 字符"
    elif _NON_ENGLISH.search(text):
        fields["text"] = "只支持英语查询；中文页面不代表支持中文语义检索"
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= MAX_TOP_K:
        fields["top_k"] = f"top_k 必须是 1—{MAX_TOP_K} 的整数"
    if wordbook_id is not None and (
        isinstance(wordbook_id, bool) or not isinstance(wordbook_id, int) or wordbook_id < 1
    ):
        fields["wordbook_id"] = "wordbook_id 必须是正整数"
    if fields:
        raise InvalidQuery(fields)


def search(conn, loaded, text, top_k=5, wordbook_id=None):
    """返回 (结果, model_time_ms)。model_time_ms 只计查询编码与相似度计算。"""
    example_index = _modules()
    validate(text, top_k, wordbook_id)
    with db.transaction(conn):
        rows = examples_repo.active_examples(conn)
        allowed_words = examples_repo.words_in_wordbook(conn, wordbook_id) if wordbook_id is not None else None
    if wordbook_id is not None and allowed_words is None:
        raise InvalidQuery({"wordbook_id": "词表不存在或已停用"})
    if example_index.corpus_fingerprint(rows) != loaded.index_manifest["corpus_fingerprint"]:
        raise SearchUnavailable("启用例句已变化，索引已过期；请执行 flask build-example-index")
    try:
        started = time.perf_counter()
        query = example_index.encode(loaded.model, [text.strip()])[0]
        scores = loaded.vectors @ query
        model_time_ms = (time.perf_counter() - started) * 1000
    except example_index.TextTooLong as exc:
        raise InvalidQuery({"text": str(exc)}) from exc
    by_id = {r["id"]: r for r in rows}
    ranked = sorted(range(len(loaded.ids)), key=lambda i: -float(scores[i]))
    results = []
    for i in ranked:
        row = by_id[loaded.ids[i]["example_id"]]
        if allowed_words is not None and row["word_id"] not in allowed_words:
            continue
        results.append(
            {
                "example_id": row["id"],
                "example_key": row["example_key"],
                "text_en": row["text_en"],
                "translation_zh": row["translation_zh"],
                "cosine_similarity": round(float(scores[i]), 6),
                "sense": {k: row[k] for k in ("sense_id", "lemma", "sense_key", "part_of_speech", "definition_zh")},
            }
        )
        if len(results) == top_k:
            break
    return results, model_time_ms


def versions(loaded):
    return {
        "model_code": MODEL_CODE,
        "revision": loaded.encoder_manifest["revision"],
        "corpus_fingerprint": loaded.index_manifest["corpus_fingerprint"],
        "corpus_count": loaded.index_manifest["count"],
        "index_built_at_utc": loaded.index_manifest["built_at_utc"],
    }


def register_encoder(conn, encoder_manifest, index_manifest, weights_name):
    """在 model_versions 登记编码器（同一 revision 只能对应同一权重），返回 (id, 是否新建)。"""
    sha = encoder_manifest["files"][weights_name]["sha256"]
    row = model_repo.find_model_version(conn, MODEL_CODE, encoder_manifest["revision"])
    if row is not None:
        if row["artifact_sha256"] != sha:
            raise SearchUnavailable("该 revision 已登记为其他权重")
        return row["id"], False
    metadata = {"encoder": encoder_manifest, "index_at_registration": index_manifest}
    model_id = model_repo.insert_model_version(
        conn,
        kind="dl",
        model_code=MODEL_CODE,
        version=encoder_manifest["revision"],
        artifact_sha256=sha,
        feature_schema_version=None,
        metadata_json=json.dumps(metadata, ensure_ascii=False),
    )
    return model_id, True
