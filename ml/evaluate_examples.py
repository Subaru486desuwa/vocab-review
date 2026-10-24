"""实验四检索评价：同一语料上比较句向量检索与 TF-IDF。

Recall@3 = 前三项命中的相关例句数 / 该查询全部相关例句数；MRR@3 = 首个相关项排名的倒数（前三无命中记 0），
两者只在有相关例句的查询上平均；无相关例句的查询单独报告最高分与前三项。
"""

import json
from pathlib import Path

import numpy as np

from ml.example_index import rank

K = 3
SPLITS = ("dev", "test")
TYPES = ("paraphrase", "polysemy", "no_relevant")


def load_queries(path, corpus_keys):
    queries, seen = [], set()
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        q = json.loads(line)
        problems = []
        if q.get("query_id") in seen:
            problems.append("query_id 重复")
        if q.get("split") not in SPLITS or q.get("type") not in TYPES:
            problems.append("split 或 type 不合法")
        if not isinstance(q.get("text"), str) or not q["text"].strip():
            problems.append("text 为空")
        unknown = [key for key in q.get("relevant", []) if key not in corpus_keys]
        if unknown:
            problems.append(f"相关例句不在语料中：{unknown}")
        if (q.get("type") == "no_relevant") != (not q.get("relevant")):
            problems.append("no_relevant 查询必须且只能没有相关例句")
        if problems:
            raise ValueError(f"{path}:{number} " + "；".join(problems))
        seen.add(q["query_id"])
        queries.append(q)
    return queries


def tfidf_scores(corpus_texts, query_texts):
    from sklearn.feature_extraction.text import TfidfVectorizer

    vectorizer = TfidfVectorizer(stop_words="english", sublinear_tf=True)
    matrix = vectorizer.fit_transform(corpus_texts)
    return (vectorizer.transform(query_texts) @ matrix.T).toarray()


def _per_query(scores, keys, query):
    order = rank(scores, keys)[:K]
    top = [keys[i] for i in order]
    relevant = set(query["relevant"])
    result = {
        "query_id": query["query_id"],
        "type": query["type"],
        "text": query["text"],
        "top3": [{"example_key": keys[i], "score": round(float(scores[i]), 4)} for i in order],
    }
    if relevant:
        hits = [rank for rank, key in enumerate(top, start=1) if key in relevant]
        result["recall_at_3"] = len(hits) / len(relevant)
        result["rr_at_3"] = 1 / hits[0] if hits else 0.0
    return result


def _mean(values):
    return round(float(np.mean(values)), 4) if values else None


def evaluate(score_matrix, keys, queries):
    rows = [_per_query(score_matrix[i], keys, q) for i, q in enumerate(queries)]
    scored = [r for r in rows if "recall_at_3" in r]
    unanswerable = [r for r in rows if "recall_at_3" not in r]
    return {
        "queries": len(rows),
        "with_relevant": len(scored),
        "recall_at_3": _mean([r["recall_at_3"] for r in scored]),
        "mrr_at_3": _mean([r["rr_at_3"] for r in scored]),
        "by_type": {
            t: {
                "queries": len(group),
                "recall_at_3": _mean([r["recall_at_3"] for r in group]),
                "mrr_at_3": _mean([r["rr_at_3"] for r in group]),
            }
            for t in ("paraphrase", "polysemy")
            if (group := [r for r in scored if r["type"] == t])
        },
        "no_relevant": {
            "queries": len(unanswerable),
            "top1_scores": [r["top3"][0]["score"] for r in unanswerable],
        },
        # 平均值用未舍入的逐条结果计算，逐条结果只在输出时舍入。
        "per_query": [{**r, **{k: round(r[k], 4) for k in ("recall_at_3", "rr_at_3") if k in r}} for r in rows],
    }


def run(model, vectors, ids, rows, queries, encode):
    """encode(model, texts) 与 Web 使用同一函数；ids 与 vectors 同序。"""
    by_id = {r["id"]: r for r in rows}
    keys = [item["example_key"] for item in ids]
    texts = [by_id[item["example_id"]]["text_en"] for item in ids]
    result = {}
    for split in SPLITS:
        subset = [q for q in queries if q["split"] == split]
        query_texts = [q["text"] for q in subset]
        dl = encode(model, query_texts) @ vectors.T
        result[split] = {
            "sentence_embedding": evaluate(dl, keys, subset),
            "tfidf": evaluate(tfidf_scores(texts, query_texts), keys, subset),
        }
    return result


def render_report(result, index_manifest, annotation_status):
    lines = [
        "# 实验四评价：英语语境例句检索",
        "",
        f"编码器 {index_manifest['encoder']['repo']} @ {index_manifest['encoder']['revision']}，"
        f"语料 {index_manifest['count']} 条，指纹 `{index_manifest['corpus_fingerprint'][:16]}`，"
        f"索引构建于 {index_manifest['built_at_utc']}。",
        f"标注状态：{annotation_status}。由 `flask evaluate-example-search` 自动生成。",
        "",
        "| 集合 | 方法 | 有相关项查询 | Recall@3 | MRR@3 | 无相关项查询 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    names = {"sentence_embedding": "句向量", "tfidf": "TF-IDF"}
    for split, methods in result.items():
        for method, m in methods.items():
            lines.append(
                f"| {split} | {names[method]} | {m['with_relevant']} | {m['recall_at_3']} | {m['mrr_at_3']} "
                f"| {m['no_relevant']['queries']} |"
            )
    lines += [
        "",
        "## test 按查询类型",
        "",
        "| 类型 | 方法 | 查询 | Recall@3 | MRR@3 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for method, m in result["test"].items():
        for t, g in m["by_type"].items():
            lines.append(f"| {t} | {names[method]} | {g['queries']} | {g['recall_at_3']} | {g['mrr_at_3']} |")
    lines += ["", "## test 无相关例句查询的最高分", ""]
    for method, m in result["test"].items():
        lines.append(f"- {names[method]}：{m['no_relevant']['top1_scores']}")
    lines += ["", "## test 句向量未在前三命中的查询", ""]
    misses = [r for r in result["test"]["sentence_embedding"]["per_query"] if r.get("rr_at_3") == 0.0]
    for r in misses:
        top = "、".join(f"{t['example_key']}（{t['score']}）" for t in r["top3"])
        lines.append(f"- {r['query_id']} {r['type']}：{r['text']} → {top}")
    if not misses:
        lines.append("- 无")
    lines += [
        "",
        "## 说明",
        "",
        "- cosine_similarity 只表示语义相关程度，不是答案置信度或语法正确率；未设相似度阈值。",
        "- 查询与语料均为英语；语料与查询都是项目自编内容，规模很小，指标只反映这一演示语料。",
        "",
    ]
    return "\n".join(lines)
