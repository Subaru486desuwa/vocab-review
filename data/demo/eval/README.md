# 实验四检索评价查询

`example_queries.jsonl` 每行一条英语查询：`split`（dev 10 条、test 30 条）、`type`（paraphrase 近义改写、polysemy 多义词的某个词义、no_relevant 语料中没有相关例句）、`relevant`（相关例句的 example_key）。

当前查询与相关性标注由 AI 起草（`annotation = ai_draft_pending_human_review`），按约定须由人工逐条确认或修改（#7）后才算独立人工标注；确认后把 `annotation` 改为 `human_reviewed`，再重新运行评价。test 集在调整检索方法前冻结，相似度阈值如需设置只在 dev 上确定。默认规则：查询表达某个词义时，该词义的两条例句都算相关；语料里其他碰巧相关的例句需要人工补充。
