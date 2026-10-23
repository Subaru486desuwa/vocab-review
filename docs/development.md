# 开发规范

2026-10-23 确定。目标 2026-11-06 前完成首版、四个实验证据与报告。

## 工作流

每项任务对应一个 GitHub Issue。从 `main` 拉出 `feat/<issue号>-<短名>` 分支，提交 PR 并在正文写 `Closes #<号>`，由仓库所有者审查后 squash 合并。PR 只承载代码审查与证据，需求与讨论留在 Issue。

提交信息使用 Conventional Commits（feat/fix/docs/test/refactor/chore）：标题英文，正文可用中文，注明 Issue 号与验收编号（如 `T06`）。

合并前在 Osaka 执行完整检查：编译、ruff、pytest、`pip check`，以及 Issue 列出的验收编号。需要 MySQL 的测试在测试库上实际运行，显示为跳过的不算通过。具体命令以 README 为准。

## 运行环境

Web 与 MySQL 都通过 Docker Compose 运行：`web` 服务挂载源码，只绑定 `127.0.0.1:5000`，Mac 经 SSH 隧道访问；`db` 服务使用 mysql:8.4，演示库与测试库分开，各用最小权限账户。迁移、测试、导入等命令都在 `web` 容器内执行，实验环境证据也从容器采集。venv 方式保留为备选。

模型依赖分别放在 `requirements-ml.in`、`requirements-dl.in`，镜像通过构建参数按需安装，torch 使用 CPU 源。模型制品与原始数据位于宿主机 `artifacts/`、`data/raw/` 并挂载进容器。不含模型依赖的镜像也必须正常启动。

## 代码约定

- 标识符使用英文，并与 `GLOSSARY.md` 的英文名和表名对应（`WordSense`、`SessionItem`、`Attempt`、`LearningState`）。注释与 docstring 用中文、保持简短；界面文案用中文；错误码用英文大写（`ALREADY_SUBMITTED`）。
- 数据库：每个请求在 `flask.g` 中懒创建 PyMySQL 连接，关闭 autocommit，使用 DictCursor。service 用 `with db.transaction():` 划定事务；repository 是接收 `conn` 的普通函数，只写参数化 SQL，提交与回滚交给 service。
- 时间：业务代码通过可注入的 `clock` 取 UTC 时间，测试固定时钟验证复习规则。
- 迁移：`sql/migrations/NNNN_*.sql` 按序编号，由 `flask db upgrade` 执行并写入 `schema_migrations`（基础设施表，不计入 14 张业务表）。已合并的迁移不修改，变更追加新文件。
- 测试：pytest；需要 MySQL 的测试标记 `db`，并只连接测试库。
- 前端：Jinja 加原生 JS，一页一个小脚本，没有构建流程。重复提交由服务端幂等处理，按钮禁用只用于改善体验。

## 内容来源

演示词表、题目与例句标注为“项目自编演示 v1”，由 AI 起草、人工校对。DL 测试查询与相关性标注由人工完成，测试集在调参前冻结。评价文档如实写明起草与校对方式。

## 日程与降级

| 日期 | 内容 |
| --- | --- |
| 10/24—26 | S2 切片 ①—⑤（#2—#6），学习闭环可演示 |
| 10/27—28 | S3 / 实验三 ML |
| 10/29—30 | S4 / 实验四 DL |
| 10/31 | S5 交接 |
| 11/01—06 | 人工校对与标注、浏览器验收、报告、缓冲 |

四个实验和学习闭环（T01—T09、T14）不做降级。进度落后时按以下顺序缩减：管理员网页导入改为只保留 CLI；统计页只保留基础计数与分母；题目版本与停用只在数据层和测试中体现；DL 评价保持最少 30 条测试查询，同时压缩错误分析。

## 分工

代理负责编写 Issue 规格、实现、测试和开 PR（标签 `ready-for-agent`）。需要人工的事项单独开 Issue（标签 `ready-for-human`）：PR 审查与合并、内容校对与标注、Mac 浏览器验收及带地址栏截图、报告中的个人信息。
