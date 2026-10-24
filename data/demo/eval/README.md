# 实验四检索评价查询

`example_queries.jsonl` 每行一条英语查询：`split`（dev 10 条、test 30 条）、`type`（paraphrase 近义改写、polysemy 多义词的某个词义、no_relevant 语料中没有相关例句）、`relevant`（相关例句的 example_key）。

查询与相关性标注由 AI 起草，2026-10-24 按项目负责人决定由 AI 逐条复核（`annotation = ai_reviewed`），不是独立人工标注；人工确认后可改为 `human_reviewed` 并重新评价。复核规则：例句表达的正是查询所述含义才算相关。据此移出 d01 abandon-1-2、t05 fragile-1-2、t11 spare-1-2、t26 issue-2-2，为 t25 补充 neighbourhood-1-2。复核时已看过前一次评价结果，但检索方法与参数未作任何调整，两种方法使用同一标注；test 集不用于调参，相似度阈值如需设置只在 dev 上确定。
