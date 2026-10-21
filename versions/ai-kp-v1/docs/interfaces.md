# 给两位开发同学：目前可以直接调用什么

单角色、单场景、单玩家；正常游戏没有真人 KP 审批。
这里先实现 Python 方法，HTTP 路由和 React 页面由网页同学接；下列 HTTP 地址仍是建议。

| 网页操作 | 已有 Python 方法 | 建议地址 |
|---|---|---|
| 看有没有存档 | `keeper.get_game()` | `GET /api/game` |
| 开始或恢复 | `keeper.start()` | `POST /api/game/start` |
| 发送消息 | `keeper.handle_message(message_id,text,game_id)` | `POST /api/game/message` |
| 查消息结果 | `keeper.get_message(message_id)` | `GET /api/game/message/{id}` |
| 读聊天 | `keeper.list_messages()` | `GET /api/game/messages` |
| 读角色 | `keeper.get_character()` | `GET /api/game/character` |
| 读公开进度 | `keeper.get_progress()` | `GET /api/game/progress` |
| 明确重开 | `keeper.restart()` | `POST /api/game/restart` |

重开是改变状态的操作，网页要先让用户确认；当前方法一次调用即创建新局。
若 HTTP 层要自动重试重开请求，需要另加 restart_id 去重，目前没有此功能。

`start()` 返回 `resumed` 和 `startup_message`。网页以 `startup_message` 展示启动说明；
新局的 `opening` 是开场白，恢复旧局时 `opening` 为空字符串，不能把它当成重新开始。
已结束存档提示重新开始；暂停存档提示真人检查；有未完成消息时同时返回
`pending_message_id`，提示恢复原回复。只有调用 `restart()` 才创建新游戏。
已结束或暂停后的普通输入返回状态说明，`action_id` 为空、无规则/骰子/变化，且 version 不增加。

## 消息输入

```json
{"message_id":"msg_001","text":"我检查书桌"}
```

网页保存并传回 `start()` 返回的 game_id，例如放 X-Game-ID 请求头。
路由层不要省略这个检查；Python 允许省略 game_id 仅为了本地命令行方便。
不让网页传技能数值、骰子结果、伤害、状态变化或想揭示哪条线索。

## 消息返回

```json
{
  "game_id": "后端生成",
  "message_id": "msg_001",
  "action_id": "后端生成",
  "status": "completed",
  "reply_type": "narration",
  "reply": "根据真实结果生成的文字",
  "rolls": [],
  "changes": [],
  "character": {"hp":10,"hp_max":10,"san":55,"san_max":99},
  "new_clues": [],
  "evidence": [],
  "progress": {},
  "suggested_actions": ["观察房间", "询问管家"],
  "guidance": "你可以观察房间，或询问管家；也可以描述其他想尝试的行动。",
  "game_status": "playing",
  "version": 1,
  "mode": "demo"
}
```

角色示例省略了其他字段；实际还含属性、技能、MP、幸运和条件。
reply_type 为 narration / question / rule_explanation / takeover / review。

`review` 只在本场景已经结束时返回。用户问“复盘”“什么信息没有找到”或发送 `/review`，
可收到 `review: {text, missed_clues, discovered_clues, ending}`。
遗漏内容仅用于结束后解释；`new_clues` 仍为空，不改变角色、游戏版本或实际已获得线索。
游戏进行中和暂停时不会提供未发现内容的复盘。

书桌首次侦查失败后，公开目标的 `actions` 可增加 `careful_search`。
玩家明确选择花十分钟细查后，场景执行预先定义的补救调查，不额外掷骰。
`progress.elapsed_minutes` 表示为这种额外调查消耗的故事分钟数；普通对话不自行累计时间。
这条补救是当前场景的约定，不能当作通用规则用于所有失败检定。

question 的回答仍然作为下一条普通消息发送。
takeover 表示超出范围或发生需要真人处理的状态，不代表成功完成任意玩家要求。
网页显示新线索时展示 `description`，不要只展示线索名称。

## 下一步提示

消息结果及 `start()`、`restart()`、`get_game()` 返回两个字段：

| 字段 | 内容 | 怎么显示 |
|---|---|---|
| `suggested_actions` | 当前可以建议玩家尝试的动作列表 | 可以做成可选按钮 |
| `guidance` | 适合直接展示的中文提示 | 放在本次结果、骰子、线索和角色状态后面 |

二者表达同一组建议，网页择一展示，避免重复。提示是建议，玩家仍可以自由描述行动，
并非必须按按钮或输入固定词。建议只根据公开场景整理，过滤已完成的调查、交谈，
不会通过提示泄露隐藏线索、未触发事件或成功失败条件。

普通叙述和规则解释可以带建议；追问、需要接管、暂停或结束时返回空列表和空文字。
空 `guidance` 不显示占位提示。如果 `reply` 已含完全相同的提示文字，也不要再显示一次。

每条 evidence 有 evidence_id、text、title、source、pdf_page、printed_page、edition、score。
页码从 1 开始；未核对则为空。score 是检索排序分数，不是“答案正确率”。

## 保存、重复发送和故障

- 同一 game_id + message_id + text 返回同一结果。相同编号换 text 会报 MessageConflict。
- 已完成旧消息的回复包含当时的角色快照。网页仅用同一游戏内不低于当前 version 的快照更新面板；
  重新查看历史消息不应把角色显示倒退。需要最新状态时调用 get_game/get_character。
- 单局只处理一条行动。若回复失败，先恢复原消息，再开始新行动。
- 骰子先保存，再提交角色和场景；模型叙事失败后重试，不会重新掷骰或重复扣 SAN。
- get_message 返回 processing / completed / failed。当前 handle_message 是同步入口，
  HTTP 要先返回 processing 时由路由同学安排后台任务，不要假称这里已经实现消息队列。
- StorageError / MessageConflict 可以显示清晰提示；StaleGameError 要重新读取当前游戏。
  模型异常不应把完整 SDK 错误、请求正文或密钥直接返回网页。
- 导出、真人接管按钮、角色手工校正、撤销事件、WebSocket 尚未实现。保留为后续工作，
  不把之前 PDF 中的建议接口当作已经存在的功能。

## 和骰子同学怎么继续配合

现有 trpg 引擎不需要为 Agent 再写一套。CharacterTools 将 Character.check 的结果包装成
可序列化返回值，并检查是否达到本次要求难度。公开状态只从数据库快照读取。
规则标准按 data/agent_rules.md 的已核对范围，复杂战斗/状态恢复仍待共同决定。

当前 SQLite 层是为了先把 Agent 独立跑起来。如果队友之后提供统一存储接口，
替换 KeeperService 中的 Storage 即可；不要同时运行两个独立的角色数值来源。
