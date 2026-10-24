# 实验报告

`docs/template/` 是课程下发的四份 .doc 模板。`build_reports.py` 以模板为底稿，只填写“五、实验结果分析（实验源代码、实验结果图、探讨分析）”和“六、实验总结与思考”，模板其余内容与格式不动，生成本目录下的四份 .docx。

```bash
python3 docs/reports/build_reports.py
```

- 数字全部从 `evidence/` 读取，源码片段直接截取仓库代码；证据或代码更新后重新运行即可，不手工改报告正文。
- 封面的姓名、学号、实验时间、成绩与签字由本人填写。
- `screenshots/` 由 `node docs/reports/shoot.mjs <仓库根目录> docs/reports/screenshots chrome-headless-shell-linux-arm64/chrome-headless-shell` 在 Osaka 用本机 headless Chromium 截取（演示账户 demo，web 服务需在运行），不含浏览器地址栏；课程要求的带地址栏截图见 #8，补齐后可替换。实验一报告使用 `evidence/exp01/` 中的 Mac Chrome 截图。
- 实验四的评价查询与相关性标注由 AI 起草并经 AI 复核（#7），报告中已注明；如之后改为人工标注，重新运行 `flask evaluate-example-search`、复制结果到 `evidence/exp04/`，再生成报告。
