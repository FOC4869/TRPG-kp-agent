# 当前网页接口与消息流程

本文描述 `74d2c34` 的实际网页接口。原 CLI Python 方法参考已放到 [历史目录](history/ai-kp-v2/interfaces.md)。
安装与完整路由表见 [开发说明](development.md)。

## 开局

```http
POST /api/games
Content-Type: application/json
```

```json
{
  "requestId": "4b1c911a-d12c-41a4-83ba-72c6aa0d4e59",
  "moduleId": "rainy-archive",
  "investigatorId": "richard"
}
```

返回公开游戏状态，其中 `gameId` 是后续游戏 URL 与请求使用的编号。
同一个创建请求重复发送，内容相同会恢复同一局；内容冲突不会另开一局来掩盖问题。
目录可显示的内容与允许开局的组合是两个概念，后端再次校验，不只依赖按钮显示。

## 读取状态

`GET /api/games/{game_id}` 返回当前状态，不触发模型和行动。

| 字段 | 内容 |
|---|---|
| gameId、version | 游戏编号和当前版本 |
| module、investigator | 本局故事、人物公开资料和当前数值 |
| scene、npc、npcs | 当前地点、可显示人物及授权图片 URL |
| inventory、nearbyItems | 随身物品和当前地点可拾回的物品 |
| facts | 已获得的线索 |
| messages | 已保存的公开对话、检定、伤害及规则引用 |
| suggestions、guidance | 根据当前真实进度生成的行动提示 |
| pendingTurn | 未完成回合的原请求编号、文字和阶段 |
| pendingAction | 玩家需要确认或取消的决定 |
| ended、ending、campaignEnding | 结束状态、兼容值及原故事结局 |
| paused | 是否需要真人检查后继续 |

不会把隐藏故事定义、模型原始提示词、密钥、后台计划或尚未获得的线索作为这个投影返回。

## 发送行动

```http
POST /api/games/{game_id}/actions
Content-Type: application/json
```

```json
{
  "requestId": "85ca2394-fb3c-485c-b1b7-ee84368b0839",
  "text": "查看铁柜编号，寻找照片中的位置",
  "expectedVersion": 6
}
```

`requestId` 必须是 UUID；输入去除首尾空白后为 1–1000 字符；版本为正整数。
版本号 6 只是格式示例，实际发送前必须用本局最新版本。
恢复原回合要复用原编号和原文字，而不是生成新编号重复行动。

结束确认等操作可以另带 `confirmationId`，对应当前 `pendingAction.id`。
通过页面确认时文字为“确认执行”或“取消这次行动”。

## SSE 事件

请求通过接收检查后，返回 `text/event-stream`。
每个 JSON 事件含 `type`、`turnId` 和递增 `seq`；心跳是注释，不是正文。

| 事件 | 网页处理 |
|---|---|
| turn.started | 本轮开始 |
| turn.status | 理解／结算／生成正文等进度 |
| check.started、check.resolved | D100 检定卡与最终出目 |
| effect.resolved | 伤害表达式及真实结果，不伪装成技能检定 |
| state.updated | 已持久化的公开状态 |
| message.started、message.delta、message.completed | 正文创建、增量与完整消息 |
| turn.completed | 回合完成，使用最新状态 |
| turn.failed | 回合未完成，显示错误及恢复入口 |

```text
event: message.delta
data: {"type":"message.delta","turnId":"原请求UUID","seq":7,"messageId":"消息编号","delta":"你核对了柜门编号。"}

```

上面的编号是说明格式用的占位文字，不是可直接发送的游戏事件。
前端按序号和稳定的消息／检定编号去重，处理中文 UTF-8 拆块与流中断。
只有正文最终保存后才把本轮当作完成；HTTP 连接断开不代表服务器一定取消了行动。

## 错误与恢复

进入流之前可以返回 404、409、422、503 等 HTTP 错误。
游戏错误一般在 `detail` 中给出 code 和 message；只读目录的错误格式可为普通说明。
已经开始 SSE 后的错误通过 `turn.failed` 表达，不能只看 HTTP 200 就判定行动成功。

| 情况 | 处理 |
|---|---|
| 版本冲突 | 重新 GET，不用旧版本覆盖 |
| 原请求内容变了 | 拒绝冲突，不当成同一次恢复 |
| 上轮未完成 | 先恢复原回合，暂不发送新的行动 |
| 已结束或暂停 | 拒绝新的行动，保留历史和恢复需要的原回合 |
| 已提交但正文失败 | 保留原随机值与效果，只恢复正文 |

供应商鉴权、余额、限流等错误使用固定分类，不把原始错误正文和 Key 返回给玩家。

## 复盘与素材

结束后 `GET /api/games/{game_id}/review` 可读取已发现与遗漏线索；进行中不开放。
`GET /api/games/{game_id}/assets/{asset_id}` 只提供本局已获授权的素材。
人物头像与封面使用目录接口；前端不直接访问后端文件路径。

接口源代码：[games.py](../backend/app/api/games.py)、[modules.py](../backend/app/api/modules.py)。
前端契约：[types/game.ts](../frontend/src/types/game.ts)、[api/game.ts](../frontend/src/api/game.ts)。
