# 答辩演示脚本

对应 `docs/acceptance.md` 的答辩路径。每一步分清**规则结果**（服务端判分、复习规则与统计，来自 MySQL 中的作答事实）与**模型输出**（实验三、四，只记录在 `inference_events`，不改变学习记录）。全程约 8 分钟，内容为“项目自编演示 v1”。

## 演示前检查（汇报前一天与当天各一次）

在 Osaka 仓库根目录：

```bash
docker compose up -d
```

```bash
docker compose run --rm web flask rebuild-learning-state
```

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5000/lab/hello
```

- Mac 建立隧道 `ssh -N -L 5000:127.0.0.1:5000 osaka`，浏览器打开 `http://127.0.0.1:5000/`。
- 用一个**新注册账户**演示（如 `defense1`），统计从零开始，能看到“未测试”。已有的 demo 账户保留了留证时的作答，适合在第 5 步后对照。
- `/lab/ml` 显示模型可用、`/examples` 能检索；否则按 README 执行 `flask register-model artifacts/ml` 与 `flask build-example-index` 后重启 web。
- 另开一个终端准备第 9 步的 MySQL 查询。
- 万一 Osaka 或隧道不可用：`docs/reports/screenshots/` 的截图与 `evidence/exp02/review-path.txt` 的完整 HTTP 记录作为备用材料。

## 路径

| 步 | 操作 | 应看到 | 讲解要点 |
| --- | --- | --- | --- |
| 1 | 首页 → “查看 Flask 基础演示” | `/lab/hello` 文字与静态图片 | 实验一：应用工厂、蓝图路由、Jinja 模板、静态资源 |
| 2 | `/register` 注册新账户并登录 | 跳转概览；统计全部为未测试 | 实验二：密码只存 Werkzeug 哈希；错误密码与不存在用户统一 401 |
| 3 | `/wordbooks` 只选六级演示词表 | 词表来源、版本、词条数 | 目标词表只是关联；词条不等于覆盖其所有词义 |
| 4 | 导航“今日” → `/today` → “学今日新词（10 个）”，故意答错前 2 题；做完点“返回今日任务” | 新词义 0 / 10 → 10 / 10，显示已完成、连续学习 1 天；每题即时判分，重复点击提交不重复计数 | **规则结果**：今日新词义只出任何题型都未作答的词义，“今天”按用户时区；服务端按固定题目版本判分，同答案重试返回原结果、换答案 409 |
| 5 | `/review` | 2 道错题约 10 分钟后到期；到期后今日任务出现“复习辨义（2）”并变回未完成 | **规则结果**：复习时间由作答记录按复习规则计算，可由 `flask rebuild-learning-state` 从作答事实重建核对 |
| 6 | `/dashboard` → 回到 `/wordbooks` 增加雅思 → `/dashboard` | 合计词条中共有词只计一次；雅思下已练习的共有词条复用六级作答 | 切换目标不删除历史；未练习的词义、题型仍显示未测试，不推断掌握 |
| 7 | `/lab/ml` 输入 间隔 1 天、历史 5 次、正确 4 次；再输入历史 0 次 | 预期练习正确比例与模型版本、耗时；历史 0 次显示冷启动、无估计值 | **模型输出**：随机森林估计一次练习内正确回忆比例，不是掌握度；test MAE 低于训练集均值基线（数字见 `evidence/exp03/evaluation.md`） |
| 8 | `/examples` 输入 `I need to open a savings account.`；再输入 `We sat on the grass beside the river.` | 两次分别命中 bank 的“银行”与“河岸”词义例句，附余弦相似度与编码器版本 | **模型输出**：句向量相似度只表示语境相关程度；同一词条的多义能区分，TF-IDF 对照见 `evidence/exp04/evaluation.md`；标注由 AI 起草并经 AI 复核，不是独立人工标注 |
| 9 | 终端执行下方查询 | 第 7、8 步的推理事件：类型（ml/dl）、来源、状态、模型版本、耗时 | 模型输入、输出与版本只进 `inference_events`；模型不可用时练习照常（T13） |

第 9 步查询（密码从 `.env` 读取，不显示）：

```bash
set -a; . ./.env; set +a; docker compose exec -T -e MYSQL_PWD="$DB_PASSWORD" db mysql -u"$DB_USER" "$DB_NAME" -e "SELECT e.id, e.kind, e.source_type, e.status, m.model_code, m.version, e.model_time_ms, e.created_at FROM inference_events e LEFT JOIN model_versions m ON m.id = e.model_version_id ORDER BY e.id DESC LIMIT 5"
```

## 可能的追问

| 问题 | 回答依据 |
| --- | --- |
| 用户数据从哪来？ | 只来自用户在本系统的作答；今日任务让用户每天回来练习，数据随之积累。公开数据只用来训练实验三模型，不代表本系统用户；`GLOSSARY.md` 的今日任务、今日新词义、连续学习天数 |
| 今日任务算不算掌握？ | 不算：新词义答错也计入，连续天数只看每天是否作答；完成状态查看时计算，错题到期后变回未完成（T15，`tests/test_today.py`） |
| 双击或并发提交会不会重复计分？ | T06：作答表对题目实例唯一，作答与统计同一事务；`tests/test_practice.py::test_concurrent_identical_submissions_count_once` |
| 写入中途出错会怎样？ | T08：注入异常后整笔回滚；`tests/test_practice.py::test_failure_before_state_update_rolls_back_everything` |
| 题目改了旧练习还能解释吗？ | T10：题目版本不可原地修改，旧练习引用旧版本；`tests/test_practice.py::test_old_session_keeps_original_question_version` |
| 模型挂了还能学吗？ | T13：干净环境未放模型时练习可用、模型接口 503，见 `evidence/handoff/clean-env.txt` |
| ML 有没有数据泄漏？ | 按全局时间 70/15/15 切分、同一时间戳不跨集合，特征只用作答前历史，测试集最后使用；`docs/models.md`、`evidence/exp03/evaluation.md` |
| 怎么在别的机器复现？ | README 启动步骤；`scripts/handoff_check.sh` 从干净副本全新启动并检查；SQL 导出见 `sql/export/` |
