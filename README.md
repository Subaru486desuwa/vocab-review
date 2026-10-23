# 词汇诊断与个性化复习系统

面向六级、考研和雅思的 Python Web 课程项目。以统一词库连接三类目标词表，记录辨义、拼写和语境练习，再生成可解释的复习计划。

**当前可运行：首页、`/lab/hello`、静态图片，以及 Docker 中的 MySQL 与 14 张业务表迁移。** 已整理完整首版架构与契约；账户、学习业务、内容导入、ML 和 DL 后续实现。仓库保持 **private**。

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

当前未实现 `import-content` 或 `create-admin`，不应运行这些命令。真实配置只放本地 `.env` 或环境变量。

## 从哪里继续开发

| 文档 | 用途 |
| --- | --- |
| [架构](docs/architecture.md) | 模块职责、依赖方向、模型隔离 |
| [首版范围](docs/requirements.md) | 四个课程实验及功能边界 |
| [数据模型](docs/data-model.md) | ER 图、14 张表、历史与事务规则 |
| [接口契约](docs/api.md) | 页面、JSON 接口、状态码、幂等提交 |
| [模型契约](docs/models.md) | 共享特征、离线评价、索引版本与留证 |
| [实施与验收](docs/acceptance.md) | S0—S5、T01—T14、M01—M06 |
| [术语表](GLOSSARY.md) | 词条、词义、题型、作答与学习状态 |
| [开发规范](docs/development.md) | 分支与提交、合并前检查、Docker、代码约定、日程 |

```text
app/          Flask 应用、路由、业务、SQL 查询、模板与静态资源
ml/           离线训练、特征构建、模型评价
artifacts/    本地模型与向量；二进制制品不进入 Git
sql/          按序迁移（已有 0001 建表）与演示种子（后续实现）
data/demo/    演示词库与来源（后续准备）
tests/        实际入口与回归检查
evidence/     四次实验的真实截图、日志和评价索引
docs/         架构、契约、验收与 ADR
```

## 检查当前骨架

合并前在 `web` 容器中执行：

```bash
docker compose run --rm web sh -c 'python -m compileall -q app tests && ruff check . && ruff format --check . && pytest -v && pip check'
```

标记为 `db` 的测试使用 `TEST_DB_*` 指定的独立测试库，每次运行先清空再迁移；库名必须以 `_test` 结尾。未配置测试库时这些测试显示为跳过，不算通过；已配置但无法连接时报错。当前检查覆盖基础页面、安全配置、迁移、约束、连接生命周期与事务回滚；业务与模型测试随对应切片加入。

`requirements.in` 是 Web 直接依赖，`requirements.lock.txt` 是实际安装版本；`requirements-dev.in`/`requirements-dev.lock.txt` 另含 pytest 与 ruff，镜像默认安装。算法依赖将在模型阶段独立验证后加入，不在基础页面启动时下载或训练模型。

## 资料与协作

架构依据《词汇诊断与个性化复习系统 开发交接报告》v1.0（2026-10-22）；报告中的建议参数、规模和阈值保留为起点，不作为教师硬性要求或已完成结果。任务使用本仓库 GitHub Issues；协作约定见 [AGENTS.md](AGENTS.md)。

实现依据：[Flask 应用工厂](https://flask.palletsprojects.com/en/stable/patterns/appfactories/)、[Flask 安装](https://flask.palletsprojects.com/en/stable/installation/)、[Flask-WTF CSRF](https://flask-wtf.readthedocs.io/en/1.2.x/csrf/)。
