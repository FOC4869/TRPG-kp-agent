# 历史材料怎么用

旧版材料保留原来的失败输出、测试范围和当时结论，用来说明项目怎样迭代。
当前写实现方法时看 [架构](../architecture.md) 和 [Agent](../agent-design.md)，写最新结果时看 [当前实验索引](../evaluation/README.md)。

| 历史资料 | 报告用途 |
|---|---|
| [v2 问题修复原记录](ai-kp-v2/问题发现与修复记录.md) | 14 类早期问题的现象、原因、改法与验证限制 |
| [v2 泛化测试](ai-kp-v2/泛化测试结果_2026-10-21.md) | 相同 23 例关键词／真实模型比较，原始模型与应用保护后评分 |
| [v1 检测报告](ai-kp-v2/evaluation/v1_history_report.md) | 单书房阶段、结构化输出排错、底层规则边界 |
| [原始结果目录](ai-kp-v2/evaluation) | JSON、失败与修后日志、当时的用户反馈截图 |
| [旧 CLI 接口](ai-kp-v2/interfaces.md) | 从 Python 服务向当前网页接口演进的背景 |
| [旧模型配置](ai-kp-v2/model_setup.md) | 旧版设置记录，实际运行采用当前 model_setup.md |
| [搬入清单与校验和](ai-kp-v2/source-manifest.json) | 每份材料的原来源及改动范围 |

## 与当前版不同的地方

- 旧资料中的 `ai-kp-v2/.env`、根目录 `kp_agent/`、`tests/` 等路径，已经变为 `backend/` 下的结构。
- 旧版以 CLI 和 SQLite 为主要入口，当前展示是 React／FastAPI／SSE 和 JSON 存档。
- 旧版单书房、三地点、当前网页是不同阶段；v1 的 270 项和 v2 的 98 项不能写成当前测试数量。
- 旧记录说“这批补丁没有真实模型复测”，是当时的限制；现在有独立的 2026-10-26 网页 API 测试，不能反过来修改旧实验结论。
- 旧版只有止血包的理查德初始化已被修正，当前还包含原卡四件个人物品。
- 页面继续使用 AI 直接主持；旧规划里的人类 KP 每轮审批、多 Agent 或 MCP 设想不代表当前实现。

搬入时保留了原始 JSON、日志和截图；Markdown 增加历史说明，并修正到当前代码的链接。
这些链接供查看现在如何处理，不表示旧实验一定运行过当前网页代码。

## 队友旧版资料在哪里

队友的原 main 完整保存在 [backup/team-main-20261026](https://github.com/FOC4869/TRPG-kp-agent/tree/backup/team-main-20261026)。
其中与当前界面有关的设计来源可以查：

- [首页设计](https://github.com/FOC4869/TRPG-kp-agent/blob/a3724a5e9ff81bec3c7d019f8c9a0287037e6697/docs/design/done/homepage.md)
- [人物选择页](https://github.com/FOC4869/TRPG-kp-agent/blob/a3724a5e9ff81bec3c7d019f8c9a0287037e6697/docs/design/done/investigator-selection.md)
- [模组库](https://github.com/FOC4869/TRPG-kp-agent/blob/a3724a5e9ff81bec3c7d019f8c9a0287037e6697/docs/design/done/module-library.md)
- [继续调查入口](https://github.com/FOC4869/TRPG-kp-agent/blob/a3724a5e9ff81bec3c7d019f8c9a0287037e6697/docs/design/done/resume-investigation.md)
- [状态变化提示](https://github.com/FOC4869/TRPG-kp-agent/blob/a3724a5e9ff81bec3c7d019f8c9a0287037e6697/docs/design/done/game-state-feedback.md)

当前说明已按现有代码重写，不把备份分支的另一套运行流程、十一地点可玩测试或旧功能计数搬成当前成绩。
