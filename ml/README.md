# 离线模型工作区

实验三（ML）：

- `features.py`：recall_features_v1，训练与 Web 推理共用。
- `prepare_recall_data.py`：从 `data/raw/settles.acl16.learning_traces.13m.csv.gz` 生成 `data/processed/recall_v1/`。
- `train_recall.py`：训练随机森林，写出 `artifacts/ml/`（模型、清单、指标、评价报告）。

```bash
docker compose run --rm web python -m ml.prepare_recall_data
```

```bash
docker compose run --rm web python -m ml.train_recall
```

原始数据从 Harvard Dataverse（doi:10.7910/DVN/N8XJME，CC BY-NC 4.0）下载到 `data/raw/`，与处理结果、模型文件一起留在本地，不进 Git。改变抽样、切分、特征或超参数前，先确认与已记录结果的可比性；新制品使用新版本号。

实验四（DL）：

- `download_encoder.py`：固定 revision 下载编码器到 `artifacts/dl/encoder/`，核对 SHA-256。
- `example_index.py`：长度检查、编码、语料指纹、索引构建与校验，Web 共用。
- `evaluate_examples.py`：Recall@3、MRR@3 与 TF-IDF 对照；由 `flask evaluate-example-search` 调用。
