"""学习诊断的模型算法：薄弱项 KMeans 分组与错题语义层次聚类。不训练新模型，输入为已有制品的输出。"""

import numpy as np

GROUP_COUNT = 3
MIN_GROUP_ITEMS = 6
SEED = 42
# 约为 v2 演示语料全部词义两两余弦相似度的第 99 百分位；启发式阈值，未经标注评价。
SIMILAR_THRESHOLD = 0.45
GROUP_NAMES = ("薄弱", "一般", "较稳")


def group_items(features, expected_recall):
    """对 词义 × 题型 的特征（recall_features_v1）与预测值标准化后 KMeans 分 3 组。

    按组内平均平滑正确率升序（同值再按平均预测值）编号，0 为“薄弱”；不足 MIN_GROUP_ITEMS 项或
    不同取值少于 3 种时返回 None。
    """
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    x = np.column_stack([np.asarray(features, dtype=np.float64), np.asarray(expected_recall, dtype=np.float64)])
    if len(x) < MIN_GROUP_ITEMS or len(np.unique(x, axis=0)) < GROUP_COUNT:
        return None
    labels = KMeans(n_clusters=GROUP_COUNT, n_init=10, random_state=SEED).fit_predict(StandardScaler().fit_transform(x))
    means = [tuple(float(np.mean(x[labels == k, c])) for c in (3, 4)) for k in range(GROUP_COUNT)]
    rank = {k: i for i, k in enumerate(sorted(range(GROUP_COUNT), key=lambda k: (means[k], k)))}
    return [rank[int(label)] for label in labels]


def cluster_senses(vectors, threshold=SIMILAR_THRESHOLD):
    """L2 归一化向量按余弦距离做平均链接层次聚类，簇间平均相似度高于 threshold 才合并。

    返回每个向量的簇下标；少于 2 个向量时各自成簇。
    """
    vectors = np.asarray(vectors, dtype=np.float64)
    if len(vectors) < 2:
        return list(range(len(vectors)))
    from sklearn.cluster import AgglomerativeClustering

    model = AgglomerativeClustering(
        n_clusters=None, metric="cosine", linkage="average", distance_threshold=1 - threshold
    )
    return [int(label) for label in model.fit_predict(vectors)]


def cosine(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
