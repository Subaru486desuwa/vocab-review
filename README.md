# 词汇诊断与个性化复习系统

面向六级、考研和雅思的 Python Web 课程项目。以统一词库连接三类目标词表，记录辨义、拼写和语境练习，再生成可解释的复习计划。

**当前可运行：首页、`/lab/hello`、静态图片、注册/登录/退出、`flask create-admin`、内容包导入与演示内容、目标词表选择、今日任务（到期复习、每日 10 个新词义、连续学习天数）、三类题型练习与服务端判分、复习计划与统计、学习状态重建核对、实验三 ML（`/lab/ml`）与实验四 DL（`/examples`），以及 Docker 中的 MySQL 与 14 张业务表迁移。** 干净环境启动、SQL 导出与备份恢复已脚本化（见“交接、导出与备份”），答辩步骤见 [演示脚本](docs/demo.md)；分级背单词等平台功能后续实现（#17）。仓库保持 **private**。

## 先运行基础页面

在 Osaka Linux ARM64 上使用 Docker Compose 验证：`web`（Python 3.12）与 `db`（MySQL 8.4）。

```bash
git clone https://github.com/Subaru486desuwa/vocab-review.git
cd vocab-review
cp .env.example .env
```

编辑 `.env`，为 `SECRET_KEY`、`DB_PASSWORD`、`TEST_DB_PASSWORD`、`MYSQL_ROOT_PASSWORD` 填入随机值，并把 `HOST_UID`/`HOST_GID` 改为 `id -u`/`id -g` 的结果。数据库账户只在数据卷首次初始化时创建，之后修改密码需同步修改 MySQL 账户。

```bash
docker compose up -d --build
```

```bash
docker compose run --rm web flask db upgrade
```

在浏览器打开 `http://127.0.0.1:5000/`，点击“查看 Flask 基础演示”。若从 Mac 浏览器查看 Osaka 上的页面，先在 Mac 建立隧道：

```bash
ssh -N -L 5000:127.0.0.1:5000 osaka
```

`flask db upgrade` 只对 `.env` 中 `DB_NAME` 指定的库执行未应用的迁移，已执行的版本记录在 `schema_migrations`。基础页面不连接数据库，不设数据库也能启动。

备选 venv 方式：`python3 -m venv .venv`、`source .venv/bin/activate`、`python -m pip install -r requirements-dev.lock.txt` 后运行 `flask --app app:create_app run --host 127.0.0.1 --port 5000`。Docker 的 `db` 端口不对宿主机开放，venv 方式需要自备 MySQL 并修改 `DB_HOST`/`DB_PORT`。Windows 尚未验证。

应用要求 `SECRET_KEY`，未设置时拒绝启动。管理员只能用命令创建，密码在终端隐藏输入：

```bash
docker compose run --rm web flask create-admin
```

导入演示内容并创建演示学习者（密码取自 `.env` 的 `DEMO_USER_PASSWORD`）：

```bash
docker compose run --rm web flask import-content data/demo/v1
```

```bash
docker compose run --rm web flask import-content data/demo/v2
```

v1 是首次发布的内容包，v2 在其上新增题目版本与例句修订（见 [data/demo/README.md](data/demo/README.md)），两者按顺序导入。

```bash
docker compose run --rm web flask seed-demo-user
```

实验三需要先在本地准备数据并训练（原始数据与模型不进 Git，步骤见 [模型契约](docs/models.md)），然后登记制品：

```bash
docker compose run --rm web flask register-model artifacts/ml
```

实验四先下载固定 revision 的编码器（约 88 MB，需联网），再按当前例句构建索引；例句变化后需重新构建：

```bash
docker compose run --rm -e HF_HUB_OFFLINE=0 web python -m ml.download_encoder
```

```bash
docker compose run --rm web flask build-example-index
```

```bash
docker compose run --rm web flask evaluate-example-search
```

核对学习状态投影与作答记录（加 `--apply` 修复差异）：

```bash
docker compose run --rm web flask rebuild-learning-state
```

`import-content` 先整批预检，有错误时逐行报告且不写入；加 `--dry-run` 只报告变化。格式见 [内容包格式](docs/content-format.md)。真实配置只放本地 `.env` 或环境变量。

## 交接、导出与备份

从干净副本全新启动并逐项检查（构建、迁移、导入、公开页面、答辩路径、无模型时 T13、登记模型后推理、完整检查、导出与恢复），结束后删除临时项目与数据卷；使用 5001 端口，不影响正在运行的演示环境：

```bash
scripts/handoff_check.sh
```

导出全部表结构与内容表数据（不含账户、练习、作答、学习状态与推理事件）到 `sql/export/vocab_review_content.sql`，可直接导入空库：

```bash
scripts/db_export.sh
```

完整备份（含账户哈希与学习记录）写到被 Git 忽略的 `backups/`，文件权限 600：

```bash
scripts/db_backup.sh
```

恢复到指定库；库不存在时创建，同名表被替换。恢复到演示库 `vocab_review` 会覆盖当前数据，先另做一次备份，恢复后运行 `flask rebuild-learning-state` 核对：

```bash
scripts/db_restore.sh backups/vocab_review-20261024T000000Z.sql vocab_review_restore
```

三个数据库脚本在 `db` 容器内以 root 执行，密码经容器环境变量传入，不出现在命令行或日志中。

## 从哪里继续开发

| 文档 | 用途 |
| --- | --- |
| [架构](docs/architecture.md) | 模块职责、依赖方向、模型隔离 |
| [首版范围](docs/requirements.md) | 四个课程实验及功能边界 |
| [数据模型](docs/data-model.md) | ER 图、14 张表、历史与事务规则 |
| [接口契约](docs/api.md) | 页面、JSON 接口、状态码、幂等提交 |
| [模型契约](docs/models.md) | 共享特征、离线评价、索引版本与留证 |
| [实施与验收](docs/acceptance.md) | S0—S5、T01—T14、M01—M06 |
| [演示脚本](docs/demo.md) | 答辩路径、演示前检查与追问依据 |
| [内容包格式](docs/content-format.md) | 导入文件、预检规则与题目版本 |
| [术语表](GLOSSARY.md) | 词条、词义、题型、作答与学习状态 |
| [开发规范](docs/development.md) | 分支与提交、合并前检查、Docker、代码约定、日程 |

```text
app/          Flask 应用、路由、业务、SQL 查询、模板与静态资源
ml/           离线训练、特征构建、模型评价
artifacts/    本地模型与向量；二进制制品不进入 Git
sql/          按序迁移与内容导出（sql/export/）
scripts/      干净环境验收、SQL 导出、备份与恢复
data/demo/    演示内容源表、生成脚本与 v1/v2 内容包（AI 起草、AI 复核）
tests/        实际入口与回归检查
evidence/     四次实验的真实截图、日志和评价索引
docs/         架构、契约、验收与 ADR
```

## 检查当前骨架

合并前在 `web` 容器中执行：

```bash
docker compose run --rm web sh -c 'python -m compileall -q app tests && ruff check . && ruff format --check . && pytest -v && pip check'
```

标记为 `db` 的测试使用 `TEST_DB_*` 指定的独立测试库，每次运行先清空再迁移；库名必须以 `_test` 结尾。未配置测试库时这些测试显示为跳过，不算通过；已配置但无法连接时报错。检查覆盖基础页面、安全配置、迁移与约束、账户、导入、练习与作答事务、复习与统计、实验三与实验四。

`requirements.in` 是 Web 直接依赖，`requirements.lock.txt` 是实际安装版本；`requirements-dev.in`/`requirements-dev.lock.txt` 另含 pytest 与 ruff；`requirements-ml.*` 与 `requirements-dl.*`（torch 取 CPU 源）分别是实验三、四依赖。镜像默认都安装，`WITH_ML=0 WITH_DL=0 docker compose build` 构建不含模型依赖的镜像，此时实验页显示不可用，其余功能照常。算法依赖将在模型阶段独立验证后加入，不在基础页面启动时下载或训练模型。

## 资料与协作

架构依据《词汇诊断与个性化复习系统 开发交接报告》v1.0（2026-10-22）；报告中的建议参数、规模和阈值保留为起点，不作为教师硬性要求或已完成结果。任务使用本仓库 GitHub Issues；协作约定见 [AGENTS.md](AGENTS.md)。

实现依据：[Flask 应用工厂](https://flask.palletsprojects.com/en/stable/patterns/appfactories/)、[Flask 安装](https://flask.palletsprojects.com/en/stable/installation/)、[Flask-WTF CSRF](https://flask-wtf.readthedocs.io/en/1.2.x/csrf/)。
