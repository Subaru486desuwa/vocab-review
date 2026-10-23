"""下载实验四的句向量编码器到本地（固定 revision，只取 safetensors 权重、分词器与配置）。

python -m ml.download_encoder [--out artifacts/dl/encoder]

Web 与索引构建只从本地目录加载（离线模式），不在请求中下载。
"""

import argparse
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

REPO = "sentence-transformers/all-MiniLM-L6-v2"
REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
LICENSE = "apache-2.0"
FILES = [
    "README.md",
    "config.json",
    "config_sentence_transformers.json",
    "modules.json",
    "sentence_bert_config.json",
    "1_Pooling/config.json",
    "model.safetensors",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "vocab.txt",
]
OUT = Path("artifacts/dl/encoder")
MANIFEST = "encoder_manifest.json"


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download(out=OUT):
    from huggingface_hub import HfApi, hf_hub_download

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    info = HfApi().model_info(REPO, revision=REVISION, files_metadata=True)
    expected = {s.rfilename: s.lfs.sha256 for s in info.siblings if s.lfs is not None}
    files = {}
    for name in FILES:
        cached = hf_hub_download(REPO, name, revision=REVISION)
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cached, target)
        digest = sha256_file(target)
        if name in expected and expected[name] != digest:
            raise SystemExit(f"{name} 的 SHA-256 与 Hugging Face 记录不符")
        files[name] = {"bytes": target.stat().st_size, "sha256": digest, "lfs_verified": name in expected}
    manifest = {
        "repo": REPO,
        "revision": REVISION,
        "license": LICENSE,
        "source": f"https://huggingface.co/{REPO}/tree/{REVISION}",
        "downloaded_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": files,
    }
    (out / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=OUT)
    manifest = download(parser.parse_args(argv).out)
    for name, f in manifest["files"].items():
        print(f"{name} {f['bytes']} {f['sha256'][:16]}{' (LFS 校验通过)' if f['lfs_verified'] else ''}")


if __name__ == "__main__":
    main()
