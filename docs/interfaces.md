# 网页游戏 API 与事件契约

2026-10-24，已实现。目录见 [catalogue-api](catalogue-api.md)，独立网页运行器见 [ADR-0004](decisions/ADR-0004-web-game-runtime.md)，多模组与工具边界见 [ADR-0005](decisions/ADR-0005-module-driven-runtime.md)。旧 CLI 保留自身 SQLite 流程，方法参考 [历史 CLI 文档](history/cli-interface-reference.md)。

## HTTP

| 方法与路径 | 输入／行为 |
|---|---|
| GET /api/health | 不初始化游戏或模型 |
| POST /api/games | `{requestId: UUID, moduleId, investigatorId}`，返回公开快照 |
| GET /api/games/{game_id} | 完整公开历史、当前状态和未决回合 |
| POST /api/games/{game_id}/actions | `{requestId: UUID, text: 1..1000字, expectedVersion: integer, confirmationId?: UUID}`，返回 SSE |
| GET /api/games/{game_id}/assets/{asset_id} | 仅返回已揭示的配置允许图片 |

创建请求 ID 确定性映射 game_id；相同 ID／相同参数去重，不同参数 409。创建成功进入 `#/game?game=<game_id>`，刷新只 GET。游戏状态每次提交增加 version，包括纯问答；未决回合必须先恢复。结束游戏拒绝新行动，允许读取和相同请求重试。

同 ID／同文本优先于期望版本检查，复用正在运行的任务或已完成回复；同 ID／不同文本或不同 confirmationId 409。同局有未完成行动时新请求 409。无未决回合时陈旧 version 返回 409。空白输入、不合法 UUID、超长输入或额外字段 422；未找到 404；损坏存档、资料或配置故障 503。错误 detail 为 `{code,message}`，不返回内部路径或供应商错误正文。

公开快照：gameId/version/module/investigator（当前资源与模板公开资料）/scene/npc/npcs/inventory/facts/messages/suggestions/ended/ending/endingSummary/status/pendingTurn/pendingAction/nearbyItems。pendingTurn 只有 requestId/text/stage 及确认回合可选 confirmationId；pendingAction 仅公开 id/prompt，nearbyItems 仅含当前场景放下的物品；无原始计划、条件、未揭示事实、模板原文件或密钥。module包含id/title及可选englishTitle，scene.region来自该模组配置；无英文名时前端隐藏副标题。消息支持 keeper/npc/player/check/effect，具有稳定 id；check 保存 checkId/skill/target/reason/roll/success/result/details。effect 保存 effectId/resource/dice/amount/before/after/reason，为独立伤害骰而非 D100。

## SSE

每条 `event: <type>` 和 JSON `data:`，含 turnId、递增 seq。15 秒注释心跳。前端 POST fetch 读取流，不用只支持 GET 的原生 EventSource。

| 事件 | 额外数据 |
|---|---|
| turn.started | 回合开始 |
| turn.status | stage: understanding/resolving/narrating |
| check.started | check: checkId/skill/target/reason |
| check.resolved | check: 出目、普通成败和损失明细 |
| effect.resolved | effect: 已保存的独立 HP 伤害骰与前后资源值 |
| state.updated | state: 已提交公开快照 |
| message.started | message: 稳定 ID 的空白 Keeper 消息，恢复可重置 |
| message.delta | messageId/delta |
| message.completed | message: 已保存的完整正文 |
| turn.completed | state: 最终快照 |
| turn.failed | code/message，可恢复，绝不当成检定失败 |

DeepSeek失败使用固定的公开分类：`model_authentication_failed`（密钥认证）、`model_insufficient_balance`（余额）、`model_rate_limited`（限流）、`model_request_rejected`（请求格式）、`model_unavailable`（服务不可用）、`model_timeout`（超时）、`model_connection_failed`（连接）及`model_invalid_plan`（返回格式）。不透传供应商原始异常或请求内容；均保留原请求供问题解决后恢复。

检定与效果落盘后才发布 resolved；损失骰是 details（例如 SAN 1D6=3），不是额外 D100。多个检定依次发布。前端持续读流，将结果揭示、状态和叙述排队展示；约0.8秒动画只影响展示，减少动态效果直接显示。历史检定不重播，按checkId去重。

危险行动先保存公开后果与确认编号，不投骰。按钮提交 confirmationId 和“确认执行”／“取消这次行动”；自然语言明确同意也可由 Agent 映射。问题保留确认，另一实际行动取消旧确认，撤离确认与危险确认互斥。陈旧按钮返回409 confirmation_expired；同一确认回合恢复必须保留原 confirmationId。伤害出目先保存、状态一次提交，再发布 effect.resolved；前端按 effectId 去重，历史结果静态显示。

断线不取消后台任务；重新读取快照后提交原 ID／原文本。未完成正文重新生成，已保存出目和已提交效果不重做。无需 token 持久重放。单次模型请求45秒、整轮120秒，不自动重试供应商；用户明确恢复才继续。结案在最终回复保存后弹窗，复用最终正文。

非安全场景撤离与模组定义的代价确认提示由运行器按配置和实际状态生成，使用同一消息事件协议，不调用叙述模型、不提前执行；收到下一次明确确认后才结算。普通结果叙述使用当前公开场景、条件描述及在场NPC允许知识，避免初始描述覆盖已提交进度。创建与读取响应为 `Cache-Control: private, no-store`。

## 运行边界

仅本地单进程／单 worker；根目录进程锁加同局接收锁。后台任务与订阅者分离，未决回合序列化状态。游戏 URL 是本地恢复凭证，不是互联网账号鉴权。不能把此服务直接视为多人上线方案。素材与存档目录均未静态挂载。

运行器按每局模组加载已注册的v2配置，HTTP层不识别具体剧情。已登记的v1存档只在内存转换，GET无写盘；下一次原子保存升级，历史出目／效果保持。未知指纹返回409 version_incompatible，配置错误返回503 profile_invalid，均保留存档。
