"""recall_features_v1：训练与 Web 推理共用的特征转换，列顺序与定义见 docs/models.md。"""

import math

import numpy as np

FEATURE_SCHEMA_VERSION = "recall_features_v1"
FEATURE_NAMES = ("log_delta_days", "log_seen", "log_correct", "smoothed_accuracy")
SECONDS_PER_DAY = 86400
MAX_COUNT = 1_000_000


def validate_recall_input(delta_seconds, history_seen, history_correct):
    """返回字段 → 错误说明；为空表示合法。计数为非负整数且 history_correct ≤ history_seen。"""
    fields = {}
    if isinstance(delta_seconds, bool) or not isinstance(delta_seconds, int | float):
        fields["delta_seconds"] = "delta_seconds 必须是数值（秒）"
    elif not math.isfinite(delta_seconds) or delta_seconds < 0:
        fields["delta_seconds"] = "delta_seconds 必须是非负有限数值"
    for name, value in (("history_seen", history_seen), ("history_correct", history_correct)):
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_COUNT:
            fields[name] = f"{name} 必须是 0—{MAX_COUNT} 的整数"
    if not fields and history_correct > history_seen:
        fields["history_correct"] = "history_correct 不能大于 history_seen"
    return fields


def is_cold_start(history_seen):
    """没有历史作答时不估计，返回冷启动。"""
    return history_seen == 0


def build_recall_features(delta_seconds, history_seen, history_correct):
    """标量或等长数组均可，返回形状为 (n, 4)、按 FEATURE_NAMES 排列的 float64 数组。

    delta_seconds 以秒为单位，先换算为天再取 log1p。
    """
    delta = np.atleast_1d(np.asarray(delta_seconds, dtype=np.float64))
    seen = np.atleast_1d(np.asarray(history_seen, dtype=np.float64))
    correct = np.atleast_1d(np.asarray(history_correct, dtype=np.float64))
    return np.column_stack(
        [
            np.log1p(delta / SECONDS_PER_DAY),
            np.log1p(seen),
            np.log1p(correct),
            (correct + 1) / (seen + 2),
        ]
    )
