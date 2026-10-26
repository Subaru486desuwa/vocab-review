# 演示内容包

`v3/` 是当前最新的演示内容：200 个词条、215 个词义（15 个多义词）、430 条例句、645 道已发布题目；三个演示词表各 80 个词条，其中 20 个三表共有。以下先说明 v1、v2，再说明 v3。

`v1/` 是可直接导入的演示内容：六级、考研、雅思三个演示词表，各 30 个词条，其中 10 个三表共有；共 70 个词条、79 个词义（9 个多义词按词义分别出题）、158 条例句（每个词义两条，实验四检索语料）、237 道题（每个词义各一道辨义、语境、拼写题）。格式与导入规则见 `docs/content-format.md`。

来源标注为“项目自编演示 v1（AI 起草，待人工校对）”，不代表任何官方考纲或完整词表。2026-10-24 按项目负责人决定，由 AI 逐条复核并修正（#7），未经人工校对，所以来源字段保持原文。

`v1/` 是首次发布的内容包，保持不变；`v2/` 是复核后的完整内容包，在 v1 之上发布：9 道语境题改为只有一个正确答案（互换或改写例句，并在出题时排除近义干扰词 significant/crucial/fundamental、diminish/undermine），diminish 释义改为“减弱；变小”以免拼写题与 decline 混淆，修正 2 条例句与译文。内容变化的 17 道题目版本号加一，正文变化的 13 条例句换用 content_version `demo-v2`。withdraw、spare 的两层含义仍各算一个词义。新库先导入 v1 再导入 v2。

- `source/extra_examples.csv` 为每个词义补充第二条例句；`source/entries.csv` 是词条、词义与题目的编辑入口：每行一个词义，`example_en` 中用 `[...]` 标出目标词，`books` 列出所属词表，`spelling_variants` 用 `|` 分隔可接受的拼写变体。
- `build_demo.py` 由它生成 `v2/`，并与 `v1/` 比对决定题目版本与例句 content_version；干扰项按题目键固定随机，同一输入总得到同一输出。修改后重新运行 `python data/demo/build_demo.py`，测试会检查 `v2/` 与源表一致、只在 v1 之上新增版本。
- 辨义题干扰项取同词性、其他词条的释义；语境题干扰项取同词性的其他词条，空格前为 a/an 时只取首字母元音性一致的词。语义上是否可能同样成立需要人工确认。

## v3 扩充词库（#38）

2026-10-26 按项目负责人决定扩充：`source/entries_v3.csv` 与 `source/extra_examples_v3.csv` 新增 130 个词条、136 个词义（三表共有 10 个，六级、考研、雅思各 40 个，偏高阶；advocate、cultivate、exploit、objective、budget、lecture 按词义分别出题），每个词义两条例句、三类题各一道；utilize/utilise、enrol/enroll、globalisation/globalization 写入拼写题的可接受答案。新例句来源为“项目自编演示 v3（AI 起草，AI 复核）”、content_version `demo-v3`；三个词表版本仍为 v1，只追加成员关系。

- v3 在 v2 之上发布，已有 237 道题、158 条例句与 v2 完全相同：`entries.csv` 的词义只在原 79 个词义里取干扰项。新词义从全部词义里取干扰项，辨义与语境题都排除 `build_demo.py` 中 `SYNONYMS_V3` 的同组近义词。
- AI 复核：逐条检查 136 道新语境题与 136 道新辨义题，发现约 20 道题的干扰项也能填入或意思重叠，补充近义词组（如 carbon/pollution、tentative/preliminary、paradox/phenomenon、cautious/skeptical），并改写 paradigm、hinder、modest、objective（形容词）、transform 的例句。未经人工校对。
- 实验四的检索评价仍以 v2 的 158 条例句为准（`evidence/exp04`）：新增例句没有相关性标注，加入语料后不重新报告指标。导入 v3 后旧索引会被拒绝，需执行 `flask build-example-index`。

导入演示库：

```bash
docker compose run --rm web flask import-content data/demo/v1
```

```bash
docker compose run --rm web flask import-content data/demo/v2
```

```bash
docker compose run --rm web flask import-content data/demo/v3
```
