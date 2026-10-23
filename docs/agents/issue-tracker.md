# Issue tracker: GitHub

本项目任务与规格保存在 `Subaru486desuwa/vocab-review` 的 GitHub Issues；在仓库内使用 `gh`。

- 创建：`gh issue create --title "标题" --body-file /path/to/body.md`
- 读取：`gh issue view <number> --json number,title,body,labels,comments`
- 列表：`gh issue list --state open --json number,title,labels`
- 评论：`gh issue comment <number> --body "内容"`
- 标签：`gh issue edit <number> --add-label "标签"`
- 关闭：`gh issue close <number> --comment "结果与证据"`

仓库由当前 Git remote 确定。技能要求“发布到 issue tracker”时创建 GitHub Issue；要求“读取任务”时按编号读取。

## Pull requests as a triage surface

**PRs as a request surface: no.**
