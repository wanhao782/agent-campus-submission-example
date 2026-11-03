# 企业知识问答 Agent

小影校招 AI Agent 开发考核第 3 题。项目面向查询制度或产品信息的员工，使用合成知识库查找可靠答案，给出文档 ID 和原文片段，并明确资料缺口和任务状态。

## 安装与离线运行

在仓库根目录运行。需要 Python 3.11 或更高版本，代码和测试均使用标准库。离线模式使用用例自带的动作序列执行同一套工具和校验逻辑。

```powershell
python -m pip install --disable-pip-version-check -r requirements.txt
python -m src.cli --mode mock --variant clear --input examples/01_clear/input.json --mock-actions examples/01_clear/mock-actions.json
python -m unittest discover -s tests -v
```

## 真实模型运行

先在当前 shell 配置 `DASHSCOPE_API_KEY`。默认使用阿里云百炼北京兼容端点和 `qwen3.8-flash`。配置名称见 [.env.example](.env.example)。可以用 `AGENT_MODEL` 更换模型。如需自定义支持 JSON 模式的兼容服务，同时配置 `AGENT_BASE_URL` 和 `AGENT_API_KEY`。CLI 读取进程环境变量。

```powershell
python -m src.cli --mode real --variant clear --input examples/01_clear/input.json
python -m examples.run --mode real --case 01_clear --case 02_conflict --output-dir review-runs
```

输入文件包含 `question` 和可选 `history`。历史消息含 `role` 和 `content`，见 [追问用例](examples/05_follow_up/input.json)。CLI 默认使用含冲突资料的 `conflict`，可用 `--variant clear` 或 `--variant revised` 对照。`--output` 和 `--trace` 可分别保存结果与运行记录。问答结果通过 `status` 区分回答、追问、资料外、工具失败和未完成。

复跑全部离线用例可执行 `python -m examples.run --mode mock --output-dir review-runs`。传入 `--output-dir` 可以保留仓库内的原始记录。真实与离线证据分别标为 `real` 和 `mock`。

## 评审入口

- [需求与验收](docs/01-requirements.md)列出六项必验场景、对照实验和提交材料。
- [技术方案](docs/02-solution.md)定义工具、决策循环、引用校验、冲突处理和运行边界。
- [实际运行与评估](docs/03-evaluation.md)逐项链接输入、输出、Trace 和测试结果。
- [AI 使用与贡献](docs/04-ai-usage.md)和[复盘](docs/05-retrospective.md)记录开发和验证过程。
