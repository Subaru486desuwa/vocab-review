# 实验报告

`docs/template/` 是课程下发的四份 .doc 模板。`build_reports.py` 以模板为底稿，只填写“五、实验结果分析（实验源代码、实验结果图、探讨分析）”和“六、实验总结与思考”，模板其余内容与格式不动，生成本目录下的四份 .docx。

```bash
python3 docs/reports/build_reports.py
```

- 数字全部从 `evidence/` 读取，源码片段直接截取仓库代码；证据或代码更新后重新运行即可，不手工改报告正文。
- 封面的姓名、学号、实验时间、成绩与签字由本人填写。
- `screenshots/` 由 `node docs/reports/shoot.mjs <仓库根目录> docs/reports/screenshots chrome-headless-shell-linux-arm64/chrome-headless-shell` 在 Osaka 用本机 headless Chromium 截取（演示账户 demo，web 服务需在运行），不含浏览器地址栏。实验一的两张图与实验二的登录失败图直接使用 `evidence/exp01/`、`evidence/exp02/` 中带地址栏的 Mac Chrome 截图（#8）。`e2_trend.png` 从 `evidence/exp02/daily-dashboard.png` 裁出“近 14 天”表格（模拟演示数据，与 `daily-http.txt` 对应），不由 `shoot.mjs` 生成。
- 实验四的评价查询与相关性标注由 AI 起草并经 AI 复核（#7），报告中已注明；如之后改为人工标注，重新运行 `flask evaluate-example-search`、复制结果到 `evidence/exp04/`，再生成报告。
