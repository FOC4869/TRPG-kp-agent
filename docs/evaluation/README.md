# 实验材料索引与数字解释

## 当前网页主版本

代码基线：`74d2c34`。最完整的文字说明是 [2026-10-26 测试报告](2026-10-26-test-report.md)。

| 文件 | 方法与范围 | 结果 |
|---|---|---|
| [initial-run.json](initial-run.json) | 首轮独立 HTTP 测试，含真实 API、系统随机数与后续级联问题 | 32 通过、8 未通过；30 次 API |
| [full-pass.json](full-pass.json) | 修复后完整重跑，含三类结局 | 62/62；53 次 API |
| [final-full-pass.json](final-full-pass.json) | 补入理查德个人物品后再跑完整路线 | 61/61；47 次 API |
| [supplement-initial.json](supplement-initial.json) | 补测首次脚本误把卡片名“理智”断言为 SAN | 实际产品结算正确，该断言失败；保留记录 |
| [supplement-pass.json](supplement-pass.json) | 理智、真实受伤治疗、注入中断后的恢复、结束提示 | 10/10 |
| [supplement-pass-summary.json](supplement-pass-summary.json) | 上项的调用量与预置进度说明 | 8 次 API，真实观察到受伤 |
| [provider-call-metadata.json](provider-call-metadata.json) | 以上排障／重跑全部调用的阶段与用量 | 139 次，454,875 total tokens；首轮 1 次无效结构 |
| [frontend-checks.json](frontend-checks.json) | lint/typecheck/build 与 4 份适配脚本的原输出 | 全部返回 0 |
| [equipment-correction.json](equipment-correction.json) | 用户要求后对两份已有存档补缺项的核对 | 每局补四项，资源、剧情、回合和消息不变 |

223 项是最终后端离线 unittest 数量，包含底层规则、原 CLI、故事与网页检查。
61 是一次完整 HTTP 流程中的断言／检查步骤数量，不是模型独立答题数。
10 项补测也包含 HTTP、确定输出和故障恢复检查，不能把 61+10 写成 71 次模型请求。
最后完整重跑与通过补测合计 55 次 API；139 次还包含较早通过轮和排障，不能说全都来自最后一轮。

随机检查失败会增加补查步骤，所以两次正常完成的流程分别有 62 与 61 项检查。
恢复补测的中断是本地主动注入，恢复正文使用真实供应商；不是声称观察到了真实供应商断网。

## 历史实验：可以写迭代，不能冒充当前成绩

| 阶段 | 原记录 | 可讨论的内容 |
|---|---|---|
| 早期单书房 v1 | [旧报告](../history/ai-kp-v2/evaluation/v1_history_report.md) | 初始格式错误、SAN 规则与保存边界；测试总数只适用于当时版本 |
| 2026-10-21 v2 规划比较 | [泛化报告](../history/ai-kp-v2/泛化测试结果_2026-10-21.md) | 相同 23 例：关键词 14/23、模型原始与应用结果 21/23 |
| v2 定向修复 | [原结果](../history/ai-kp-v2/evaluation/deepseek_targeted_after_fix.json) | 4 例：原始模型 3/4、应用保护后 4/4 |
| v2 数字说明 | [自动检查](../history/ai-kp-v2/evaluation/live_service_automatic_checks.json)、[修后算例](../history/ai-kp-v2/evaluation/live_numeric_after_fix.json) | 自动结构通过仍漏掉“30≤27”语义错误；确定工具修复 |
| v2 提示／状态与语言保护 | [状态检查摘要](../history/ai-kp-v2/evaluation/state_review_summary.json) | 当时 98 项离线检查通过；25 例关键词输入仍只通过 16 例 |

早期 23 例规划实验采用人工构造的已公开进度，不是真的掷骰一路通关。
4 例定向复测没有重跑全部 23 例，因此不能写成“修后 23/23”。
旧模型检查、当前模型检查和用户个人试玩分别记录，不强行相加为一个累计账单。

## 报告适合使用的三张表

1. **方法与功能表**：语言理解、规则依据、确定数值、持久化分别由谁负责，可参考 [架构](../architecture.md)。
2. **问题前后对照表**：原问题、失败证据、修复、验证方法，可参考 [问题记录](../问题发现与修复记录.md)。
3. **实验范围表**：版本、输入／流程数量、是否真实模型、是否固定出目、是否人工评阅，以及结果。

当前没有独立的检索标注集、正式用户满意度调查、无 RAG 对照或多 Agent 对照。
不能凭这些功能测试计算出上述实验的准确率或提升百分比。
