# 实验三评价：预期练习正确比例回归

制品 recall_rf v1，特征 recall_features_v1，训练于 2026-10-23T14:46:14Z（32.8 秒）。由 `python -m ml.train_recall` 自动生成。

## 数据

- 来源：Duolingo halflife-regression learning traces（CC BY-NC 4.0），文件 SHA-256 `26cf9b33f2e9b2e8aa9a8f262a017b30699ca2f625c56a12ce699d4ea7076873`。
- 行数：原始 12854226，英语 5014791，通过检查 5014779，抽样后 252587。
- 抽样：按用户，种子 42，比例 0.05，2190 / 43805 名用户。
- 检查未通过（一行可违反多条）：missing_value 0，history_seen_not_positive 0，delta_negative 0，session_seen_not_positive 0，history_correct_out_of_range 0，session_correct_out_of_range 0，p_recall_out_of_range 0，p_recall_mismatch 0，exact_duplicate 12，removed_total 12。

| 集合 | 行数 | 用户 | 时间范围（UTC） | 标签均值 |
| --- | --- | --- | --- | --- |
| train | 176832 | 1726 | 2013-02-28T20:15:25Z — 2013-03-09T01:52:41Z | 0.895839 |
| validation | 37867 | 555 | 2013-03-09T01:53:20Z — 2013-03-10T22:41:57Z | 0.869198 |
| test | 37888 | 625 | 2013-03-10T22:42:15Z — 2013-03-12T16:13:17Z | 0.891605 |

## 逐记录误差

| 集合 | 方法 | MAE | RMSE |
| --- | --- | --- | --- |
| validation | 随机森林 | 0.182031 | 0.283216 |
| validation | 训练集标签均值 | 0.19604 | 0.307499 |
| validation | 平滑历史正确率 | 0.236821 | 0.306941 |
| test | 随机森林 | 0.169456 | 0.266237 |
| test | 训练集标签均值 | 0.177831 | 0.277384 |
| test | 平滑历史正确率 | 0.232062 | 0.296642 |

## test 子群

| 子群 | 行数 | 方法 | MAE | RMSE |
| --- | --- | --- | --- | --- |
| history_seen<=3 | 8912 | 随机森林 | 0.169258 | 0.263729 |
| history_seen<=3 | 8912 | 训练集标签均值 | 0.171814 | 0.263997 |
| history_seen<=3 | 8912 | 平滑历史正确率 | 0.292823 | 0.329149 |
| delta>30d | 2925 | 随机森林 | 0.195711 | 0.291531 |
| delta>30d | 2925 | 训练集标签均值 | 0.184156 | 0.289632 |
| delta>30d | 2925 | 平滑历史正确率 | 0.249372 | 0.315724 |

## test 误差最大的 10 条

| lexeme | 间隔（天） | 历史 见/对 | 本次见 | p_recall | 预测 |
| --- | --- | --- | --- | --- | --- |
| `am/be<vbser><pri><p1><sg>` | 0.01 | 298/291 | 1 | 0.0 | 0.9816 |
| `dogs/dog<n><pl>` | 0.01 | 745/717 | 1 | 0.0 | 0.975 |
| `is/be<vbser><pri><p3><sg>` | 0.0 | 27/27 | 1 | 0.0 | 0.9698 |
| `woman/woman<n><sg>` | 0.01 | 259/249 | 1 | 0.0 | 0.9667 |
| `eats/eat<vblex><pri><p3><sg>` | 0.01 | 100/95 | 1 | 0.0 | 0.9637 |
| `skirts/skirt<n><pl>` | 0.0 | 140/136 | 1 | 0.0 | 0.9623 |
| `we/prpers<prn><subj><p1><mf><pl>` | 0.0 | 19/19 | 1 | 0.0 | 0.9621 |
| `does/do<vbdo><pri><p3><sg>` | 0.01 | 24/24 | 1 | 0.0 | 0.9615 |
| `is/be<vbser><pri><p3><sg>` | 0.0 | 221/209 | 1 | 0.0 | 0.9609 |
| `bear/bear<n><sg>` | 0.0 | 22/22 | 1 | 0.0 | 0.9584 |

## 说明

- 标签是一次练习内的正确回忆比例，不是掌握度、考试分数或严格校准的单次正确概率。
- 时间切分只说明对后续时间段的表现；同一用户可同时出现在训练与测试中，不能据此推断对新用户的泛化。
- 公开数据按 lexeme 计数，本系统按词义与题型计数，两者不直接等同；实验页输入为手工样例（manual_lab）。
- 特征重要性：log_delta_days 0.2976，log_seen 0.2869，log_correct 0.0575，smoothed_accuracy 0.358。
