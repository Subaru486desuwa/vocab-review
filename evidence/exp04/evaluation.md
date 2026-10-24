# 实验四评价：英语语境例句检索

编码器 sentence-transformers/all-MiniLM-L6-v2 @ 1110a243fdf4706b3f48f1d95db1a4f5529b4d41，语料 158 条，指纹 `5d7dcbadcb029b7c`，索引构建于 2026-10-24T17:00:16Z。
标注状态：AI 起草并经 AI 复核，不是独立人工标注。由 `flask evaluate-example-search` 自动生成。

| 集合 | 方法 | 有相关项查询 | Recall@3 | MRR@3 | 无相关项查询 |
| --- | --- | --- | --- | --- | --- |
| dev | 句向量 | 8 | 0.6875 | 0.7917 | 2 |
| dev | TF-IDF | 8 | 0.375 | 0.4792 | 2 |
| test | 句向量 | 27 | 0.6914 | 0.9259 | 3 |
| test | TF-IDF | 27 | 0.3457 | 0.5741 | 3 |

## test 按查询类型

| 类型 | 方法 | 查询 | Recall@3 | MRR@3 |
| --- | --- | --- | --- | --- |
| paraphrase | 句向量 | 18 | 0.6667 | 0.9167 |
| polysemy | 句向量 | 9 | 0.7407 | 0.9444 |
| paraphrase | TF-IDF | 18 | 0.4167 | 0.713 |
| polysemy | TF-IDF | 9 | 0.2037 | 0.2963 |

## test 无相关例句查询的最高分

- 句向量：[0.3062, 0.2815, 0.1639]
- TF-IDF：[0.5355, 0.4943, 0.0]

## test 句向量未在前三命中的查询

- t18 paraphrase：Lower prices encourage people to buy more. → decline-1-1（0.5768）、reluctant-1-2（0.5419）、significant-1-1（0.5336）

## 说明

- cosine_similarity 只表示语义相关程度，不是答案置信度或语法正确率；未设相似度阈值。
- 查询与语料均为英语；语料与查询都是项目自编内容，规模很小，指标只反映这一演示语料。
