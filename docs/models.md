# 模型与评价契约

Web 仅加载受信任本地制品并推理，训练和向量构建离线进行。ML 与 DL 部分均已实现，并完成真实训练/索引构建与评价（结果见 `evidence/exp03/`、`evidence/exp04/`）；DL 评价查询目前为 AI 草拟标注，待人工确认（#7）。

## ML：预期练习正确比例

使用 RandomForestRegressor 预测 Duolingo 源任务的 p_recall，字段名 expected_recall。标签表示一次练习内正确回忆比例，可为小数；不解释为掌握度、考试分数或严格校准的单次正确概率。

训练和推理共享 `ml/features.py` 的 `build_recall_features()`（输入秒，输出 (n, 4) 数组）；recall_features_v1 固定列顺序：

| 特征 | 变换 |
| --- | --- |
| log_delta_days | log1p(delta_seconds/86400) |
| log_seen | log1p(history_seen) |
| log_correct | log1p(history_correct) |
| smoothed_accuracy | (history_correct+1)/(history_seen+2) |

delta_seconds 为非负有限数值；计数为非负整数，history_correct≤history_seen。无历史或不能可靠计算间隔时返回 status=cold_start、expected_recall=null；非法输入 422。当前练习的 session_correct、p_recall 和未来记录不能进入特征。

公开数据按 lexeme 计数，本系统按词义与题型计数，不直接等同。实验页来源为 manual_lab，不改写真实学习状态；个人日志适配需要单独定义聚合粒度并验证跨域用途。随机森林不保证时间单调，不用它反求最优复习时间。

### 离线处理与评价

- 从官方入口取数据，记录来源与原始文件哈希；筛选 learning_language=en，保留时间戳。
- 检查 history_seen>0、delta≥0、session_seen>0、计数与标签范围；核对 p_recall 和 session_correct/session_seen，记录缺失、冲突、重复处理数量。
- 开发阶段可固定种子抽取用户并保留时间序列，记录规模和抽样规则。
- 按全局时间约 70/15/15 切分 train/validation/test，同一时间戳不跨集合；测试集最后使用。
- 建议起点：n_estimators=200、max_depth=12、min_samples_leaf=10、random_state=42；不作为已验证最优参数。
- 对照训练集标签均值与平滑历史正确率，报告逐记录 MAE/RMSE、样本数、时间范围及高误差/稀疏/长间隔样例。时间切分不自动证明新用户泛化。
- 同一制品核对离线与 Web 输出一致；模型无改善时保留规则复习并照实报告。

实现：`python -m ml.prepare_recall_data` 生成 `data/processed/recall_v1/`（英语过滤、规则检查、按用户 5% 抽样、时间切分、data_manifest.json）；`python -m ml.train_recall` 训练并写出 `artifacts/ml/` 的 model.joblib、manifest.json、metrics.json、evaluation.md。导出前把预测改为单线程，使离线与 Web 输出逐位一致；manifest 保存一组参考输入的预测供核对。

交付 model.joblib、训练配置、共享特征、依赖锁（`requirements-ml.lock.txt`）、数据清单、评价和 manifest.json；记录真实制品 SHA-256、模型/特征版本、时间切分、数据哈希和 Python/scikit-learn/NumPy/joblib 版本。只加载来源可信且校验通过的本项目制品；缺失或版本不符返回 503。

加载流程（`app/services/recall_model.py`）：读取 `ML_MODEL_DIR/manifest.json` → 核对 kind、特征版本、scikit-learn 版本与制品 SHA-256 → 核对 `model_versions` 中已登记且 active 的同一版本与哈希（`flask register-model artifacts/ml` 登记；同一版本号不能登记不同制品）→ `joblib.load`。每个进程成功后缓存，失败不缓存。哈希校验必须在加载前完成：被篡改的压缩制品可使 `joblib.load` 长时间卡住。

## DL：英语语境例句检索

首版模型为 sentence-transformers/all-MiniLM-L6-v2，固定 revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`（Apache-2.0）；`python -m ml.download_encoder` 只下载 safetensors 权重、分词器与配置到 `artifacts/dl/encoder/` 并核对 SHA-256。web 容器设置 `HF_HUB_OFFLINE=1`，只从本地加载。目标向量为 384 维；查询和语料均为英语。默认 256 word pieces 的长度约束在编码前核对，超限返回 422，不静默截断。中文页面不代表支持中文语义检索。

例句经人工校对，保存稳定 ID、目标词义、来源与正文版本。按稳定 ID 编码，向量保存为 L2 归一化 float32，绑定模型 revision、语料哈希与 ID 映射。每个推理进程加载一次模型和索引；查询同样归一化，按相似度降序取结果、同分按 example_key 升序（Web 与离线评价共用 `ml.example_index.rank`，换库后例句 id 不同排名也不变），再回查 MySQL 的有效内容。top_k 限 1—10，可按目标词表过滤。

模型、向量和语料版本不一致则 503，普通词典查询继续可用，不用关键词结果冒充 DL。cosine_similarity 只表示语义相关程度。

实现：`flask build-example-index` 从 MySQL 读取启用例句（词条、词义也须启用），编码前用分词器核对长度，写出 `artifacts/dl/index/`（vectors.npy、ids.json、index_manifest.json），并在 `model_versions` 登记编码器（kind=dl、version=revision、artifact_sha256=权重哈希）。Web 每个进程加载一次编码器；索引清单变化时重新载入索引；每次检索都用当前启用例句重算语料指纹（例句 id、example_key、content_version、正文哈希），与索引不一致即 503，直到重建。未设相似度阈值。`flask evaluate-example-search` 用同一编码函数与索引计算句向量与 TF-IDF（stop_words=english、sublinear_tf）指标。

### 独立检索评价

开发集和测试集分开。建议至少 30 条独立人工标注测试查询，覆盖近义表达、不同词义、无相关例句，不把目标例句原文复制为全部查询。同语料 TF-IDF 为对照。

- Recall@3：前三项命中的相关例句数 / 该查询全部标注相关例句数，再按查询汇总。
- MRR@3：首个相关项排名的倒数平均，无命中记 0。
- 无相关项查询单独报告，不混入上述相关性分母。

记录标注规则、查询数、语料规模、模型/索引版本和错误分析。相似度阈值如有需要，只在开发集确定。

## 耗时与数据库记录

两类推理保存 request_id、输入快照、模型/特征或语料版本、输出、状态和耗时；失败时不能伪装成功。模型加载失败允许 model_version_id 为空。

分开记录首次加载与预热后耗时。建议固定输入集至少 30 次顺序请求，报告 p50/p95、失败数、硬件与软件环境；该次数是项目建议，不是教师门槛。model_time_ms 只计模型计算；processing_time_ms 为请求进入至输出生成，不含写日志和网络。完整 HTTP 耗时由独立客户端测量，以 request_id 关联。

官方依据：[Duolingo](https://github.com/duolingo/halflife-regression)、[随机森林回归](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestRegressor.html)、[制品持久化](https://scikit-learn.org/stable/model_persistence.html)、[模型卡](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)、[Semantic Search](https://sbert.net/examples/sentence_transformer/applications/semantic-search/README.html)。
