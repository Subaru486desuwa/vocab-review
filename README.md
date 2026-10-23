# 词汇诊断与个性化复习系统

面向六级、考研和雅思的 Python Web 课程项目。以统一词库连接三类目标词表，记录辨义、拼写和语境练习，再生成可解释的复习计划。

**当前可运行：首页、`/lab/hello` 和静态图片。** 已整理完整首版架构与契约；账户、MySQL 学习业务、内容导入、ML 和 DL 后续实现。仓库保持 **private**。

## 先运行基础页面

本次基础 Web 骨架在 Osaka Linux ARM64、Python 3.12.3 验证。无需先准备 MySQL、词库或模型。

```bash
git clone https://github.com/Subaru486desuwa/vocab-review.git
cd vocab-review
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock.txt
cp .env.example .env
flask --app app:create_app run --host 127.0.0.1 --port 5000
```

在浏览器打开 `http://127.0.0.1:5000/`，点击“查看 Flask 基础演示”。

Windows PowerShell 使用 `py -m venv .venv` 创建环境，`.\.venv\Scripts\Activate.ps1` 激活，`Copy-Item .env.example .env` 复制配置，其余命令相同。Windows 尚未验证。

若从 Mac 浏览器查看 Osaka 上的页面，先在 Mac 建立隧道：

```bash
ssh -N -L 5000:127.0.0.1:5000 osaka
```

当前未实现 `init-db`、`import-content` 或 `create-admin`，不应运行这些命令。启用账户业务时必须设置随机 `SECRET_KEY` 和专用 MySQL 账户；真实配置只放本地 `.env` 或环境变量。

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
sql/          建表、顺序迁移与演示种子（后续实现）
data/demo/    演示词库与来源（后续准备）
tests/        实际入口与回归检查
evidence/     四次实验的真实截图、日志和评价索引
docs/         架构、契约、验收与 ADR
```

## 检查当前骨架

```bash
python -m compileall -q app tests
python -m unittest discover -s tests -v
python -m pip check
```

当前自动检查覆盖首页、演示页、静态图片、无数据库/模型时的基础入口、安全配置及未实现接口的状态。MySQL 事务与模型测试随对应业务实现，不能用当前结果替代。

`requirements.in` 是直接依赖；`requirements.lock.txt` 是本次实际安装版本。算法依赖将在模型阶段独立验证后加入，不在基础页面启动时下载或训练模型。

## 资料与协作

架构依据《词汇诊断与个性化复习系统 开发交接报告》v1.0（2026-10-22）；报告中的建议参数、规模和阈值保留为起点，不作为教师硬性要求或已完成结果。任务使用本仓库 GitHub Issues；协作约定见 [AGENTS.md](AGENTS.md)。

实现依据：[Flask 应用工厂](https://flask.palletsprojects.com/en/stable/patterns/appfactories/)、[Flask 安装](https://flask.palletsprojects.com/en/stable/installation/)、[Flask-WTF CSRF](https://flask-wtf.readthedocs.io/en/1.2.x/csrf/)。
