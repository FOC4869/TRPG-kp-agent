# 可游玩 MVP 实施契约

2026-10-24 已完成并验收。用户批准的实施任务，分支 feat/playable-mvp；保留工作区既有改动，不自动提交或推送。

## 文件与阶段

1. `backend/data/runtime/` 独立配置；`backend/kp_agent/gameplay/` 内容加载、JSON 存储、事件执行、公开投影；`backend/app/api/games.py` 创建/读取/素材接口。
2. 同包内 LangGraph 规划→校验→执行→叙述，DeepSeek 结构化规划及流式正文；任务管理与 SSE；前端真实创建、恢复、检定卡及队列。
3. 六场景、乔什同行/次日失踪两线，普通 D100、HP/SAN、物品和线索，完成/撤离/失败结案。
4. 离线故障/安全测试、规定工程检查、1440×900 和 1280×720 试玩及限额真实模型验证。

事件配置和规则是状态真相源。玩家每条输入只执行一个主要行动。谈话、假设、疑问、澄清不凭空推进世界；建议来自合法事件。主线不依赖可失败的可选线索。绳索绕过碎石检定、撬棍打开牢笼，失败仍可返回取工具。各威胁通过方法只能试一次；另有明确固定 3 HP 代价的强行通过。地下结束先确认，普通返回不结案。HP/SAN 归零失败；解决最终事件且乔什随行安全离开完成，否则明确结束是撤离。

## 接口

POST /api/games `{requestId,moduleId,investigatorId}`；GET /api/games/{game_id}；POST /api/games/{game_id}/actions `{requestId,text,expectedVersion}` 返回 SSE；GET /api/games/{game_id}/assets/{asset_id}。

公开状态包含 gameId/version/status/scene/npc/investigator/inventory/facts/messages/suggestions/pendingTurn/ended/endingSummary。稳定消息 ID、checkId 与 turnId 防止重复。创建失败保留请求 ID，成功导航 `#/game?game=<id>`，刷新只读。

SSE：turn.started/status、check.started/resolved、state.updated、message.started/delta/completed、turn.completed/failed。每条 data 为 JSON，带 turnId/seq。15 秒心跳。出目和效果保存后才发布 resolved。流中不含模型思考/规划。重连先 GET，复用未决请求；不换新 ID。结束后拒绝新的行动。

## 验证与复核

产品：十人、两线、三结局、自由行动与简化规则。工程：幂等、版本、并发、恢复、单 worker 限制。安全：公开投影、按揭示授权素材、路径约束和密钥隔离。QA：离线/HTTP/SSE/前端及真实模型；报告实际证据和局限。

四个阶段已完成；架构、接口、开发指南和 memory bank 已同步，验证与剩余边界见 [评估记录](../../evaluation/playable-mvp.md)。重要撤离／固定HP代价确认由运行器生成，动态场景上下文按已提交状态更新。
