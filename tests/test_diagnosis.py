"""学习诊断的纯算法：拼写错法分类、薄弱项分组与错题语义聚类（T17）。"""

import numpy as np
import pytest

from app.services.insights import edit_distance, spelling_kind

pytest.importorskip("sklearn")
from ml.diagnosis import GROUP_NAMES, MIN_GROUP_ITEMS, cluster_senses, group_items  # noqa: E402
from ml.features import build_recall_features  # noqa: E402


@pytest.mark.parametrize(
    ("answer", "kind"),
    [
        ("benefi", "missing_letter"),
        ("benefitt", "extra_letter"),
        ("benefat", "wrong_letter"),
        ("bneefit", "transposition"),
        ("bnefat", "other"),
        ("   ", "unanswered"),
    ],
)
def test_spelling_kind_covers_each_category(answer, kind):
    assert spelling_kind(answer, ["benefit"])[0] == kind


def test_spelling_kind_uses_the_closest_accepted_variant():
    assert spelling_kind("analize", ["analyse", "analyze"]) == ("wrong_letter", "analyze")
    assert edit_distance("ab", "ba") == 1 and edit_distance("", "abc") == 3


def _items():
    # (间隔天数, 作答次数, 正确次数)：三类明显不同的 词义 × 题型
    rows = [(1, 4, 1), (1, 5, 1), (2, 4, 2), (10, 3, 2), (12, 4, 3), (9, 3, 2), (3, 6, 6), (4, 5, 5), (2, 7, 7)]
    delta, seen, correct = zip(*[(d * 86400, s, c) for d, s, c in rows], strict=True)
    features = build_recall_features(delta, seen, correct)
    expected = [0.4, 0.45, 0.5, 0.6, 0.62, 0.58, 0.9, 0.92, 0.95]
    return features, expected


def test_group_items_is_stable_and_names_by_accuracy():
    features, expected = _items()
    groups = group_items(features, expected)
    assert groups == group_items(features, expected)
    assert len(groups) == len(expected) and set(groups) == {0, 1, 2}
    accuracy = features[:, 3]
    means = [accuracy[np.array(groups) == k].mean() for k in range(3)]
    assert means == sorted(means) and len(GROUP_NAMES) == 3
    assert groups[0] == 0 and groups[-1] == 2


def test_group_items_needs_enough_distinct_items():
    features, expected = _items()
    assert group_items(features[: MIN_GROUP_ITEMS - 1], expected[: MIN_GROUP_ITEMS - 1]) is None
    same = np.repeat(features[:1], MIN_GROUP_ITEMS, axis=0)
    assert group_items(same, [0.5] * MIN_GROUP_ITEMS) is None


def _unit(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


def test_cluster_senses_merges_only_similar_vectors():
    vectors = [_unit([1, 0.1, 0]), _unit([1, 0.2, 0]), _unit([0, 0, 1]), _unit([0, 1, 0.05])]
    labels = cluster_senses(vectors)
    assert labels[0] == labels[1] and len({labels[0], labels[2], labels[3]}) == 3
    assert cluster_senses(vectors[:1]) == [0]
    assert len(set(cluster_senses(vectors, threshold=0.999))) == 4
