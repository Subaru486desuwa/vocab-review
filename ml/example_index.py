"""实验四：例句向量索引的构建、校验与加载，离线构建与 Web 检索共用。

索引绑定三样东西：编码器 revision 与权重哈希、语料指纹（例句 id、example_key、content_version、正文哈希）、
向量与 id 的顺序映射。任何一项与当前状态不一致都拒绝使用，需要重建。
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ENCODER_DIR = "encoder"
INDEX_DIR = "index"
ENCODER_MANIFEST = "encoder_manifest.json"
INDEX_MANIFEST = "index_manifest.json"
VECTORS = "vectors.npy"
IDS = "ids.json"
WEIGHTS = "model.safetensors"


class IndexUnavailable(Exception):
    pass


class TextTooLong(ValueError):
    def __init__(self, tokens, limit):
        super().__init__(f"文本有 {tokens} 个 word piece，超过上限 {limit}；不截断，请缩短")
        self.tokens, self.limit = tokens, limit


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def rank(scores, keys):
    """按分数降序返回下标，同分按 example_key 升序；与例句 id 和向量顺序无关，评价与 Web 共用。"""
    return np.lexsort((np.asarray(keys), -np.asarray(scores, dtype=np.float64)))


def corpus_fingerprint(rows):
    """rows 含 id、example_key、content_version、text_en；与顺序无关。"""
    lines = sorted(
        f"{r['id']}\t{r['example_key']}\t{r['content_version']}\t{hashlib.sha256(r['text_en'].encode()).hexdigest()}"
        for r in rows
    )
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def read_json(path, missing):
    if not Path(path).is_file():
        raise IndexUnavailable(missing)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_encoder(dl_dir):
    """校验权重哈希后离线加载编码器；返回 (模型, 编码器清单)。"""
    encoder_dir = Path(dl_dir) / ENCODER_DIR
    manifest = read_json(encoder_dir / ENCODER_MANIFEST, f"缺少编码器清单 {encoder_dir / ENCODER_MANIFEST}")
    weights = encoder_dir / WEIGHTS
    if not weights.is_file() or sha256_file(weights) != manifest["files"][WEIGHTS]["sha256"]:
        raise IndexUnavailable("编码器权重缺失或哈希与清单不符")
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise IndexUnavailable("未安装深度学习依赖（构建镜像时 WITH_DL=1）") from exc
    model = SentenceTransformer(str(encoder_dir), device="cpu", local_files_only=True)
    return model, manifest


def check_length(model, text):
    tokens = len(model.tokenizer(text, add_special_tokens=True)["input_ids"])
    if tokens > model.max_seq_length:
        raise TextTooLong(tokens, model.max_seq_length)
    return tokens


def encode(model, texts):
    """先逐条核对长度再编码；返回 L2 归一化的 float32 向量。"""
    for text in texts:
        check_length(model, text)
    vectors = model.encode(list(texts), batch_size=32, normalize_embeddings=True, convert_to_numpy=True)
    return vectors.astype(np.float32)


def build(dl_dir, rows):
    """按稳定 id 编码全部启用例句，写出 vectors.npy、ids.json 与 index_manifest.json。"""
    model, encoder = load_encoder(dl_dir)
    rows = sorted(rows, key=lambda r: r["id"])
    vectors = encode(model, [r["text_en"] for r in rows])
    out = Path(dl_dir) / INDEX_DIR
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / VECTORS, vectors)
    ids = [
        {"example_id": r["id"], "example_key": r["example_key"], "content_version": r["content_version"]} for r in rows
    ]
    (out / IDS).write_text(json.dumps(ids, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    manifest = {
        "encoder": {
            "repo": encoder["repo"],
            "revision": encoder["revision"],
            "weights_sha256": encoder["files"][WEIGHTS]["sha256"],
        },
        "max_seq_length": model.max_seq_length,
        "dimensions": int(vectors.shape[1]),
        "dtype": "float32",
        "normalized": "L2",
        "count": len(rows),
        "corpus_fingerprint": corpus_fingerprint(rows),
        "vectors_sha256": sha256_file(out / VECTORS),
        "ids_sha256": sha256_file(out / IDS),
        "built_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (out / INDEX_MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def load_index(dl_dir, encoder_manifest):
    """校验索引文件哈希与编码器一致，返回 (向量, id 列表, 索引清单)。"""
    out = Path(dl_dir) / INDEX_DIR
    manifest = read_json(out / INDEX_MANIFEST, "缺少例句索引，请执行 flask build-example-index")
    if manifest["encoder"]["revision"] != encoder_manifest["revision"] or (
        manifest["encoder"]["weights_sha256"] != encoder_manifest["files"][WEIGHTS]["sha256"]
    ):
        raise IndexUnavailable("索引与编码器版本不一致，请重建索引")
    for name, key in ((VECTORS, "vectors_sha256"), (IDS, "ids_sha256")):
        if not (out / name).is_file() or sha256_file(out / name) != manifest[key]:
            raise IndexUnavailable(f"索引文件 {name} 缺失或哈希不符，请重建索引")
    vectors = np.load(out / VECTORS)
    ids = json.loads((out / IDS).read_text(encoding="utf-8"))
    if vectors.shape != (manifest["count"], manifest["dimensions"]) or len(ids) != manifest["count"]:
        raise IndexUnavailable("索引向量与 id 数量不一致，请重建索引")
    return vectors, ids, manifest
