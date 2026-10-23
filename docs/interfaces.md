# v2 给两位开发同学：怎样接 Agent＋RAG

当前 Python 源码位于 `backend/`，本页数据路径和示例工作目录均相对 `backend/`。FastAPI 骨架仅已实现 `GET /api/health`，其余 HTTP 地址仍为建议。

调查员选择页的独立前端 mock 与后续 API 适配约定见[调查员展示契约](investigator-api.md)，不代表已实现角色目录 HTTP 或游戏实例创建。

当前是一名玩家、一张固定角色卡、三个地点的原创故事，AI 直接当 KP。
默认故事在 `data/campaign.json`。你这边提供 Python 的 `KeeperService`，
网页同学负责 React／FastAPI，角色／骰子／数据库同学负责底层方案和对应实现。
目录中的现有工具与存储适配用于衔接，不要求 Agent 同学重新开发全部底层。

v2 当前 98 项离线测试已通过；此前做了真实 DeepSeek 的规划和少量整轮检查。
检查结果不等于网页已联调完成；HTTP 地址仍只是建议，目前没有这些 HTTP 路由。
具体结果及模型仍会选错的例子见 [本次检测记录](泛化测试结果_2026-10-21.md)。

## 已有 Python 方法

| 网页要做什么 | Python 方法 | 建议 HTTP 地址 |
|---|---|---|
| 看有没有当前存档 | `keeper.get_game()` | `GET /api/game` |
| 开始或恢复故事 | `keeper.start()` | `POST /api/game/start` |
| 发送玩家消息 | `keeper.handle_message(message_id, text, game_id)` | `POST /api/game/message` |
| 查看某条消息 | `keeper.get_message(message_id)` | `GET /api/game/message/{id}` |
| 看聊天记录 | `keeper.list_messages()` | `GET /api/game/messages` |
| 看角色 | `keeper.get_character()` | `GET /api/game/character` |
| 看当前公开进度 | `keeper.get_progress()` | `GET /api/game/progress` |
| 看已有物品 | `keeper.get_inventory()` | `GET /api/game/inventory` |
| 看已发现线索 | `keeper.get_clues()` | `GET /api/game/clues` |
| 看已提交行动的骰子 | `keeper.get_rolls()` | `GET /api/game/rolls` |
| 明确重开整段故事 | `keeper.restart()` | `POST /api/game/restart` |

地图信息从 `get_progress()` 的 `scene_id`、`title`、`visited_scenes`、`destinations` 取，
当前没有单独的 `get_map()` 方法。关闭服务时调用 `keeper.close()`。

```python
keeper = KeeperService(
    db_path="saves/keeper.sqlite3",
    campaign_path="data/campaign.json",
)
```

不传 `campaign_path` 时使用默认完整故事。旧书房可用 `scene_path="data/scenes/study_legacy.json"`
单独调试；`scene_path` 和 `campaign_path` 不能同时传。v1 存档不直接复用为 v2 故事存档。

## 消息传什么

```json
{"message_id":"msg_001","text":"我检查书桌"}
```

网页另传 `start()` 返回的 `game_id`，例如放请求头，再由 HTTP 层传进 `handle_message()`。
Python 参数允许省略 `game_id` 是为了本地命令行方便，网页不能跳过旧游戏编号检查。

玩家只传自己的话。不传技能值、骰子结果、伤害、物品数量、状态变化或想解锁的线索。
回答 AI 的追问、表达移动、使用物品和结束调查，都继续使用同一消息入口。

## 消息回什么

以下是字段示例，不是一次真实对话记录：

```json
{
  "game_id": "由后端生成",
  "message_id": "msg_001",
  "action_id": "由后端生成",
  "status": "completed",
  "reply_type": "narration",
  "reply": "根据已执行结果生成的文字",
  "rolls": [],
  "changes": [],
  "character": {"hp":10,"hp_max":10,"san":55,"san_max":99,"mp":11,"mp_max":11},
  "new_clues": [],
  "new_items": [],
  "scene_transition": null,
  "evidence": [],
  "progress": {
    "scene_id": "study",
    "title": "当前地点名称",
    "description": "当前允许公开的描述",
    "targets": [],
    "revealed_clues": [],
    "inventory": {},
    "visited_scenes": [],
    "destinations": []
  },
  "suggested_actions": [],
  "guidance": "",
  "game_status": "playing",
  "version": 1,
  "mode": "demo"
}
```

`character` 实际还含角色属性、技能、幸运、异常状态和日累计 SAN 损失。
`reply_type` 为 `narration`、`question`、`rule_explanation`、`takeover` 或 `review`。
`game_status` 表示整段故事的状态，不是某个房间是否调查过。

`scene_transition` 是本次地点切换信息，无切换时为 `null`；`new_items` 是本次新获得的物品。
兼容旧返回时用 `.get("scene_transition")` 和 `.get("new_items", [])`。
页面的最终显示以返回的 `progress` 为准，不通过猜测玩家消息自行切场景或扣物品。

## 场景、线索和物品怎样显示

| 字段 | 说明 |
|---|---|
| `progress.scene_id/title/description` | 当前地点 |
| `progress.targets` | 当前允许公开的交互对象及出口 |
| `progress.revealed_clues` | 截至本次结果已发现的线索 |
| `progress.inventory` | 已持有物品，字典格式：物品 id → 公开资料 |
| `progress.visited_scenes` | 已经访问过的地点 |
| `progress.destinations` | 当前允许公开的目的地信息 |
| `new_clues` / `new_items` | 本次新增内容，可用于弹出提示 |

每个库存项带 `id`、`name`、`description`、`quantity`。网页展示名称、描述和数量，
不读取物品的隐藏使用效果。`get_inventory()` 返回同一份公开库存；`get_clues()` 返回已发现线索。
`get_rolls()` 只返回已提交行动中的公开骰子，不公开内部草稿或未提交效果。

回访旧地点仍保留已完成调查、已触发事件和已取物品；网页不能因地点切换而重置它们。
已结束时 `description` 返回对应结局摘要，`targets` 和 `destinations` 为空；
`scene_id/title` 保留最后地点，已经获得的线索和物品仍可查看。不要把空目标当成读取失败。
只展示当前公开地图，不直接读取完整故事 JSON，把未到达地点、隐藏条件或未来线索提前发给玩家。

## 开始、移动、结束和复盘

`start()` 返回 `resumed`、`startup_message`。新局的 `opening` 为开场白；恢复旧局时它是空字符串。
网页显示 `startup_message`，有未完成消息时根据 `pending_message_id` 提示恢复原消息。

三个地点通过当前可用出口移动；离开当前房间通常只是切换地点。
整段故事结束后，普通输入只返回已结束说明；请求“复盘”“还有什么没找到”或 `/review`
才返回全局结束后的复盘。中途、暂停状态、刚刚离开第一个地点，都不能显示未发现真相。

`review` 解释已找到与遗漏的信息，不补发线索、奖励，不修改角色或重新打开故事。
现有复盘字段由 `review` 对象返回，网页优先展示它的公开 `text`。

`restart()` 一次调用就重开整段故事。网页在点击重开前确认用户意图。
若 HTTP 层希望自动重试重开请求，需要另加 `restart_id` 去重；当前没有该功能。

## Agent 内部怎样表达行动

这是给另外两位开发同学理解流程的字段，不是让网页直接执行的接口：

```json
{"intent":"investigate","target_id":"desk","item_id":null,"query":null,"question":null}
```

行动类型包含观察 `look`、调查 `investigate`、细查 `careful_search`、交谈 `talk`、移动 `move`、
用物品 `use_item`、结束调查 `finish`、问规则 `rule_question`、旧场景离开 `leave`、
追问 `clarify`、超出范围 `unsupported`。

`target_id` 从当前公开目标中取，不再固定为第一间书房的几个 id；
`use_item` 还需要 `item_id`，并由程序核对物品是否持有、数量和合法用法。
角色值、检定条件、获得线索与物品的条件仍来自已有工具和故事配置，不由模型自由填写。

Agent 调用流程：

> 理解玩家行动 → 缺信息则追问 → 按规则问题或实际技能检索 → 检查场景条件 →
> 调现有工具 → 保存角色与故事状态 → 只根据已经发生的公开结果叙述。

一次移动、消耗物品、发现线索都应通过已有保存流程提交。
`scene_state` 由现有存储层整体保存，包括地点和物品进度；本版没有另写一套数据库底层。

## RAG 返回和下一步提示

每条 `evidence` 有 `evidence_id`、`text`、`title`、`source`、`pdf_page`、`printed_page`、`edition`、`score`。
页码从 1 开始；未核对为 `null`。score 是排序值，不是正确率。规则库不含故事秘密。
当前为 17 个规则主题，覆盖三地点用到的范围；未收录规则仍可能没有依据。

成功等级问答新增内部只读工具 `CharacterTools.success_example(character, skill)`：
通过已有 `trpg.check` 生成门槛、假想出目等级和讲解文字，不调用随机数，不增加真实骰子记录，
不修改 HP／SAN／MP。不是新增网页接口，消息返回字段保持不变。
这类带数值的说明与本次合法 `evidence_id` 一起由程序直接显示，不经模型重新叙述；
因此通常只有一次 `plan` 请求。其他行动叙述继续使用模型。
前端照常显示 `reply` 和 `evidence`，不要把解释里的假想出目放入真实 `rolls` 面板。

`guidance` 是可直接展示的中文建议，`suggested_actions` 是同一组可选动作；
网页择一显示，保留自由输入，不必做成强制菜单。
追问、接管、暂停和结束时不显示普通行动建议。空建议不显示占位文字。

## 重复发送和出错时怎么办

- 相同 `game_id + message_id + text` 使用同一处理结果；相同编号换内容会报 `MessageConflict`。
- 同一局一次处理一条消息。失败后先恢复原消息，重试时编号、文本和游戏编号保持不变。
- 已完成旧消息包含当时快照；不要用旧 `version` 倒退更新角色、当前地点或库存面板。
  需要最新状态时重新调用 `get_game()`。
- 骰子先保存，再提交状态；叙述失败后恢复，不重复掷骰、扣 SAN 或发物品。
- `get_message()` 返回 `processing` / `completed` / `failed`。当前入口仍是同步方法，
  HTTP 若要先返回“处理中”，需要由网页／后端同学安排后台执行。
- 异步 HTTP 路由不要在事件循环里直接运行同步模型请求，应交适当的工作线程。
- `StaleGameError` 后重新读游戏编号；不要把模型 SDK 原始错误、请求正文或密钥回传网页。

目前没有 React、FastAPI、WebSocket、手工改角色、真人接管按钮、导出或撤销接口。
接下来由各自负责的同学继续，不把本说明中的建议 HTTP 地址写成已实现接口。
