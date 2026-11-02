# 考研词表（ECDICT）

`v1/` 是可导入的正式考研词表内容包（ADR 0004）：4778 个词条，其中 167 个已在演示词库中、沿用原有词义与题目；新增 4611 个词条、6034 个词义、5775 条例句、15440 道已发布题目（辨义 6034、拼写 6022、语境 3384），以及 3179 个词对（近义 1124、同族 585、形近 1470）。需在演示内容 v1—v3 之后导入：

```bash
docker compose run --rm web flask import-content data/wordbooks/postgraduate/v1
```

导入后例句变化，需重新执行 `flask build-example-index`。

## 来源与许可

| 内容 | 来源 | 许可 |
| --- | --- | --- |
| 词条、音标、中英释义 | [ECDICT](https://github.com/skywind3000/ECDICT) `ecdict.csv` 中 `tag` 含 `ky` 的词条（只取小写、字母与连字符组成的词） | MIT |
| 近义、同族 | [WordNet 3.0](https://wordnet.princeton.edu/) 同义词集与派生指针 | WordNet 3.0 License |
| 例句与译文 | [Tatoeba](https://tatoeba.org/) 英语句子、中文句子与英中链接导出；`source` 列记录句子编号 | CC BY 2.0 FR |

原始数据放在被 Git 忽略的 `data/raw/`：

```bash
curl -L -o data/raw/ecdict/ecdict.csv https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv
```

```bash
curl -L -o data/raw/wordnet/WNdb-3.0.tar.gz https://wordnetcode.princeton.edu/3.0/WNdb-3.0.tar.gz
```

Tatoeba 取 `https://downloads.tatoeba.org/exports/per_language/` 下的 `eng/eng_sentences.tsv.bz2`、`cmn/cmn_sentences.tsv.bz2`、`eng/eng-cmn_links.tsv.bz2`，放到 `data/raw/tatoeba/`。导出每周更新，重新下载后例句可能变化；v1 使用 2026-10-29 下载的版本。

## 构建

`build.py` 只在构建时需要 nltk 3.9.1 与 `averaged_perceptron_tagger_eng`（不是应用依赖，可放在临时 venv），约 3 分钟：

```bash
python data/wordbooks/postgraduate/build.py data/raw data/wordbooks/postgraduate/v1
```

同一原始数据总得到同一输出。规则：

- 词义：中文释义按词性行拆分，vt./vi./v. 合并为 v.，各行轮流取释义、最多 4 项；每词最多 3 个词性，第一个之外的实词词性若在 WordNet 语料中没有标注过则视为冷僻用法跳过。sense_key 为词性（n、v、adj……）。英文释义取 ECDICT 同词性第一条、去掉分号后的用例。
- 例句：英文 6—18 个词、不超过 140 字符，目标词以原形出现一次且不在句首，NLTK 标注的词性与词义一致；每个词义按“接近 10 个词、句子编号小”取 2 条。
- 辨义题：干扰项优先取同词性形近词的释义（最多 2 个），其余为同词性随机；排除近义词与释义有重叠的选项。
- 语境题：用第一条例句挖空；干扰项优先取同词性形近词，排除近义与同族词，空格前为 a/an 时首字母元音性一致。
- 拼写题：题干为“释义（词性），首字母 x”；与本包或演示词库的其他拼写题题干相同时不出题。
- 近义：两个词在同一 WordNet 同义词集中，且该义项对两个词都是前 2 个义项、在语料中标注过。同族：WordNet 派生指针。形近：长度 ≥4 且编辑距离 1，或长度 ≥8、前三个字母相同且距离 2；排除词形变化、只差词尾（-s、-ed、-ly 等）或否定前缀（un-、in-、dis- 等）、5 个字母以内只差首字母（fate/mate）的组合，同族词只保留等长的一处之差（advice/advise）。

题目与词对由规则生成，未经人工或 AI 逐条复核；WordNet 的近义含较宽的义项（如 flush/blush），语境题的随机干扰项也可能在句中成立。词对是内容关系，不是“易混词”认定。
