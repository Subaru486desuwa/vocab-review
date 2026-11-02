# 内容包格式

内容包是一个目录，包含下列 UTF-8 文件中的任意几个；其他文件被忽略。`flask import-content <目录>` 与 `POST /api/v1/admin/import` 使用同一套预检与写入，规则如下。

## 导入规则

- 整批先预检，报告 `文件:行号 说明`；有任何错误时不写入任何数据。预检通过后在一个事务内写入，写入中途失败整批回滚。`--dry-run` / `dry_run=1` 完成预检与写入计算后回滚，只报告变化。
- 引用可以指向同一批次或数据库中已有的内容。按业务键匹配：已存在且字段相同计为“未变”，可修改字段不同计为“更新”，否则“新增”。导入不删除任何行；停用内容写 `is_active=0`。
- `lemma_norm` 必须等于对 `lemma` 做 Unicode NFC、去首尾空白、转小写、合并内部空白的结果，显示形式保留在 `lemma`。英美拼写等变体不合并为同一词条，而是在拼写题的 `answers.accepted` 中显式列出。
- 键（code、version、sense_key、example_key、logical_key、content_version）只用字母、数字、点、下划线和连字符。`is_active` 取 1 或 0，留空为 1。

## 文件

| 文件 | 必填列 | 可选列 | 业务键与可修改字段 |
| --- | --- | --- | --- |
| wordbooks.csv | code, version, exam_type, name, source | is_active | (code, version)；可改 name、is_active。来源或考试类型变化须发布新 version |
| words.csv | lemma, lemma_norm | language（仅 en）, phonetic, is_active | lemma_norm；可改 lemma、phonetic、is_active |
| senses.csv | lemma_norm, sense_key, part_of_speech, definition_zh | definition_en, is_active | (lemma_norm, sense_key)；可改其余字段 |
| memberships.csv | wordbook_code, wordbook_version, lemma_norm, position | source_note | (词表, lemma_norm)；同一批次重复即报错；可改 position、source_note |
| examples.csv | example_key, lemma_norm, sense_key, text_en, source, content_version | translation_zh, is_active | example_key；不可换绑词义；修改 text_en 必须同时更换 content_version |
| questions.jsonl | logical_key, version, lemma_norm, sense_key, skill_type, prompt, answers, grading_policy | options, status | (logical_key, version)，见下 |
| relations.csv | lemma_norm_a, lemma_norm_b, relation_type, source | is_active | (两词条不分先后, relation_type)；relation_type 为 synonym（近义）、derivation（同族）、confusable（形近）；两词条不能相同，同一批次 a—b 与 b—a 视为重复；可改 source、is_active |

## 题目版本

每行一个 JSON 对象。已存在的 (logical_key, version) 内容（prompt、options、answers、grading_policy）必须完全相同，修改题目须新增 version，且新版本号必须是当前最大版本加一；同一批次每个 logical_key 只能出现一次。新版本以 published 写入后，同一 logical_key 的其他版本改为 retired，已发放的题目实例仍引用原版本。`status` 只对最新版本生效，被取代的旧版本保持 retired。logical_key 绑定的词义与题型不可更改。

| skill_type | options | answers | grading_policy |
| --- | --- | --- | --- |
| recognition、context | 至少两个 `{"id", "text"}`，id 互不相同 | `{"option_id": 选项 id}` | `{"type": "choice"}` |
| spelling | 省略或 null | `{"accepted": [非空字符串, ...]}` | `{"type": "text", "trim": 布尔, "case_sensitive": 布尔}` |
