import json

import numpy as np
import pytest

from ml.evaluate_examples import evaluate, load_queries

KEYS = ["a-1-1", "a-1-2", "b-1-1", "b-1-2"]


def test_recall_and_mrr_at_3():
    queries = [
        {"query_id": "q1", "type": "paraphrase", "text": "x", "relevant": ["a-1-1", "a-1-2"]},
        {"query_id": "q2", "type": "polysemy", "text": "y", "relevant": ["b-1-1", "b-1-2"]},
        {"query_id": "q3", "type": "no_relevant", "text": "z", "relevant": []},
    ]
    scores = np.array(
        [
            [0.9, 0.1, 0.8, 0.7],  # a-1-1 第 1，a-1-2 不在前三 → Recall 0.5，RR 1
            [0.9, 0.8, 0.7, 0.1],  # b-1-1 第 3 → Recall 0.5，RR 1/3
            [0.2, 0.1, 0.3, 0.4],
        ]
    )
    result = evaluate(scores, KEYS, queries)
    assert (result["with_relevant"], result["recall_at_3"], result["mrr_at_3"]) == (2, 0.5, round((1 + 1 / 3) / 2, 4))
    assert result["no_relevant"] == {"queries": 1, "top1_scores": [0.4]}
    assert result["by_type"]["polysemy"]["mrr_at_3"] == 0.3333


@pytest.mark.parametrize(
    ("query", "message"),
    [
        ({"split": "dev", "type": "paraphrase", "text": "x", "relevant": ["zz-1-1"]}, "不在语料中"),
        ({"split": "dev", "type": "no_relevant", "text": "x", "relevant": ["a-1-1"]}, "no_relevant"),
        ({"split": "train", "type": "paraphrase", "text": "x", "relevant": ["a-1-1"]}, "split"),
    ],
)
def test_query_file_is_validated(tmp_path, query, message):
    path = tmp_path / "q.jsonl"
    path.write_text(json.dumps({"query_id": "q1", **query}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_queries(path, set(KEYS))
