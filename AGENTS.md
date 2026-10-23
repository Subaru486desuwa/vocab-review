# 项目工作约定

使用简体中文沟通。当前是长期维护的 Python Web 课程项目，开发与测试在 Osaka；Mac 用于浏览器验收。

- 先阅读 `GLOSSARY.md` 和相关 `docs/adr/`；架构见 `docs/architecture.md`，接口与数据改动分别对照 `docs/api.md`、`docs/data-model.md`。
- 首版采用 Flask、Jinja、PyMySQL、MySQL。保持参数化 SQL、显式事务和题目版本；核心学习流程不依赖模型可用性。
- 修改业务行为前准备可捕获问题的检查；实现完成后集中执行编译、测试与实际入口验收。保留无关修改。
- 训练、切分、超参或数据处理变化先确认实验可比性；真实结果、演示数据和待实现内容分别记录。
- 密钥、个人学习日志、原始训练数据和模型权重保留在环境或本地文件，仓库保持 private。仅按授权推送、部署或发布。

## Agent skills

### Issue tracker

使用本仓库的 GitHub Issues。创建、读取或更新任务时，先读 `docs/agents/issue-tracker.md`。

### Triage labels

使用默认五类标签。分诊或更改标签前，先读 `docs/agents/triage-labels.md`。

### Domain docs

单上下文：根目录 `GLOSSARY.md` 与 `docs/adr/`。探索或修改领域概念前，先读 `docs/agents/domain.md`。
