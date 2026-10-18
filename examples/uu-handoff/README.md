# uu-remote-linux 开发交接摘要小工具

这是一次真实 Claude Code → EverOS → Codex CLI → EverOS → 新 Claude Code 接力开发产物，用于整理测试记录。它不修改远控服务，也不会检查证据文件是否真实存在。`有证据` 只表示输入中存在非空白证据引用，最终仍需人工核对。

- `stage-a/`：Claude 的解析器与 10 项测试，交给 Codex 时只有这两个源文件。
- `finished/`：Codex 补完的渲染、CLI 与 17 项测试。
- `sample.json`：合成演示数据，**不是任何真实机器的验收结果**。

在仓库根目录运行：

```bash
python3 examples/uu-handoff/finished/handoff_brief.py examples/uu-handoff/sample.json
python3 -m unittest discover -s examples/uu-handoff/finished -v
python3 docs/evidence/independent_acceptance.py
```

输入为 JSON 数组，每项的 `platform`、`component`、`check`、`result` 为非空白字符串，`evidence` 为字符串数组。`result` 严格等于 `passed` 且有非空白证据时标为“有证据”；passed 但无证据标为“待补证”；其他值标为“未通过”。程序保留输入次序，末行始终说明上线状态未确认。

输入或读文件错误退出 2；合法输入即便包含未通过项也退出 0。因此退出 0 只代表**摘要生成成功**，不代表所有功能验收通过。

查看[真实接力记录与边界](../../docs/real-client-relay.md)。
