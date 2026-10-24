# 演示内容包

`v1/` 是可直接导入的演示内容：六级、考研、雅思三个演示词表，各 30 个词条，其中 10 个三表共有；共 70 个词条、79 个词义（9 个多义词按词义分别出题）、158 条例句（每个词义两条，实验四检索语料）、237 道题（每个词义各一道辨义、语境、拼写题）。格式与导入规则见 `docs/content-format.md`。

来源标注为“项目自编演示 v1（AI 起草，待人工校对）”，不代表任何官方考纲或完整词表。2026-10-24 按项目负责人决定，由 AI 逐条复核并修正（#7），未经人工校对，所以来源字段保持原文。

`v1/` 是首次发布的内容包，保持不变；`v2/` 是复核后的完整内容包，在 v1 之上发布：9 道语境题改为只有一个正确答案（互换或改写例句，并在出题时排除近义干扰词 significant/crucial/fundamental、diminish/undermine），diminish 释义改为“减弱；变小”以免拼写题与 decline 混淆，修正 2 条例句与译文。内容变化的 17 道题目版本号加一，正文变化的 13 条例句换用 content_version `demo-v2`。withdraw、spare 的两层含义仍各算一个词义。新库先导入 v1 再导入 v2。

- `source/extra_examples.csv` 为每个词义补充第二条例句；`source/entries.csv` 是词条、词义与题目的编辑入口：每行一个词义，`example_en` 中用 `[...]` 标出目标词，`books` 列出所属词表，`spelling_variants` 用 `|` 分隔可接受的拼写变体。
- `build_demo.py` 由它生成 `v2/`，并与 `v1/` 比对决定题目版本与例句 content_version；干扰项按题目键固定随机，同一输入总得到同一输出。修改后重新运行 `python data/demo/build_demo.py`，测试会检查 `v2/` 与源表一致、只在 v1 之上新增版本。
- 辨义题干扰项取同词性、其他词条的释义；语境题干扰项取同词性的其他词条，空格前为 a/an 时只取首字母元音性一致的词。语义上是否可能同样成立需要人工确认。

导入演示库：

```bash
docker compose run --rm web flask import-content data/demo/v1
```

```bash
docker compose run --rm web flask import-content data/demo/v2
```
