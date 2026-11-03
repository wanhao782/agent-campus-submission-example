# 测试与评估

环境为 Windows、Python 3.12.7。真实模型使用阿里云百炼 `qwen3.8-flash`。离线动作使用 `scripted-mock`。在仓库根目录运行 `python -m unittest discover -s tests -v` 可复跑自动测试，[原始测试结果](../examples/test-results.txt)记录了 13 项通过。

## 验收记录

| 用例 | 预期与实际 | 输入与记录 |
| --- | --- | --- |
| 01 明确答案 | 返回 `answered`，以 D01 原文支持“费用发生之日起 30 天”。 | [输入](../examples/01_clear/input.json) · [输出](../examples/01_clear/output.real.json) · [真实 Trace](../examples/01_clear/trace.real.json) |
| 02 文档冲突 | D01 为 30 天，D02 为 15 天。模型逐篇读取，补查范围或优先级，仍无法裁决时以 `needs_clarification` 并列引用并追问。 | [输入](../examples/02_conflict/input.json) · [输出](../examples/02_conflict/output.real.json) · [真实 Trace](../examples/02_conflict/trace.real.json) |
| 03 资料外问题 | 宠物医疗保险未被收录，返回 `out_of_scope` 并说明资料缺口。 | [输入](../examples/03_out_of_scope/input.json) · [输出](../examples/03_out_of_scope/output.real.json) · [真实 Trace](../examples/03_out_of_scope/trace.real.json) |
| 04 相似问题改写 | 原措辞首轮无命中。模型换成报销相关词后命中 D01，读取后给出相同的 30 天结论。 | [输入](../examples/04_paraphrase/input.json) · [输出](../examples/04_paraphrase/output.real.json) · [真实 Trace](../examples/04_paraphrase/trace.real.json) |
| 05 上下文追问 | 从历史解析出差住宿发票，查到 D04 并回答返程后 7 天内提交。 | [输入](../examples/05_follow_up/input.json) · [输出](../examples/05_follow_up/output.real.json) · [真实 Trace](../examples/05_follow_up/trace.real.json) |
| 06 工具失败 | 找到 D01 候选后注入读取异常。模型观察错误并停止，返回 `tool_error`，说明缺少可核对原文。 | [输入](../examples/06_tool_failure/input.json) · [输出](../examples/06_tool_failure/output.real.json) · [真实 Trace](../examples/06_tool_failure/trace.real.json) |
| 07 文档替换 | 固定问题，替换 D01 期限与版本后，答案及原文同步从 30 天变成 45 天。与用例 02 对比，加入 D02 冲突规则后，模型增加读取及补查，最终从回答改为追问。 | [输入](../examples/07_revised/input.json) · [输出](../examples/07_revised/output.real.json) · [真实 Trace](../examples/07_revised/trace.real.json) |
| 08 执行上限 | 工具预算设为 1，下一次调用被阻止，返回 `incomplete`，实际只调用一次工具。 | [输入](../examples/08_budget/input.json) · [输出](../examples/08_budget/output.mock.json) · [离线 Trace](../examples/08_budget/trace.mock.json) |

各用例的资料变体和故障条件见[用例清单](../examples/cases.json)。八个用例另存了离线输出与 Trace，可用于无密钥评审。

## 发现的问题与改动

- `qwen-plus` 连通性测试返回 HTTP 403，错误码 `AllocationQuota.FreeTierOnly`。随后用 `qwen3.8-flash` 跑通。 [百炼免费额度说明](https://help.aliyun.com/zh/model-studio/new-free-quota)
- 一次真实冲突复跑已说明 30 天与 15 天的冲突，但把任务标成 `answered`。加强提示词，要求补查仍无裁决依据时明确追问。程序会驳回含待解决缺口的 `answer`，把错误交回模型。 [修复前输出](../examples/02_conflict/output.real.before-fix.json) · [修复前 Trace](../examples/02_conflict/trace.real.before-fix.json)
- 追问用例早期召回混入日常费用报销条款，模型额外推断了两份规则的优先关系。移除通用匹配标签并约束结论范围后复跑，核对引用与问题中的对象一致。

## 已知边界

关键词检索依赖合成资料的词项与模型改写。真实服务可能受额度、网络和模型版本影响。代码可以验证引用确实来自已读原文，也可以识别模型明确报告的待解决缺口。模型若遗漏候选证据或提出原文未支持的语义推断，仍需通过评估发现。测试通过范围为上述用例。
