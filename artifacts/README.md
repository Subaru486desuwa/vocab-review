# 本地模型制品

本地 `artifacts/ml/` 存放实验三制品（由 `python -m ml.train_recall` 生成）；`artifacts/dl/` 存放实验四的编码器（encoder/）、向量索引与 ID 映射（index/）和评价结果（eval/）。目录内制品被 Git 忽略，不上传权重或向量。模型来源与完整性验证属于制品加载契约，详见 `docs/models.md`。
