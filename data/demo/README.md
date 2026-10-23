# 演示内容包

后续准备 UTF-8 的 words.csv、senses.csv、wordbooks.csv、memberships.csv、examples.csv 与 questions.jsonl。词表记录来源、版本与使用说明；建议首批 200—500 个校对词条，包含三考试共有词与新增词，不宣称完整考纲覆盖。

- words：language, lemma, lemma_norm, phonetic。
- senses：lemma_norm, sense_key, part_of_speech, definition_zh。
- wordbooks：code, version, exam_type, source；memberships 连接词表与 lemma_norm。
- examples：lemma_norm, sense_key, text_en, source, content_version。
- questions：logical_key, version, lemma_norm, sense_key, skill_type, prompt, options, answers, grading_policy。

预检检查重复键、悬空词义、缺失词条、空答案和非法考试类型；全部通过后单批事务提交，失败回滚。固定 Unicode、首尾空白、英语大小写策略并保留原始显示形式；短语、专名和变体显式处理，不使用不可追踪的模糊去重。当前无内容数据或导入实现。
