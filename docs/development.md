# 开发、接口与内容接入

报告写作与完整说明从 [docs 入口](README.md) 阅读；详细 HTTP／SSE 见 [接口文档](interfaces.md)。

## 当前分工边界

只有一个 Agent：`kp_agent/graph.py` 的七阶段流程，网页通过 `web.py` 复用。
`models.py` 负责理解行动和生成回复，`retrieval.py` 查规则；模型不能自行填出目、加减资源或写存档。
`owned_tools.py` 读取故事与人物，调用 `campaign.py`、`trpg/` 做确定计算。前端只显示公开 API 数据。

当前可以游玩雨夜来信的三个地点和理查德；其他人物、岭下暗影及其地点只供查看。
没有接入队友的另一套 Agent，也没有复制其 Agent 源码。

## 配置

发布清单：`backend/data/module-catalogue.json`。

- `investigatorIds`：人物页可查看的名单。
- `playableInvestigatorIds`：已经开放游玩的名单；当前只有 `richard`。
- `campaignFile`：符合现有 CampaignDefinition 格式的故事文件。为空时只供查看。
- `campaignAssetDirectory`：这个故事的图片目录；素材仍按局授权，不公开整个数据目录。
- `sceneNames`：明确允许在故事介绍页显示的地点名称，不包含隐藏线索或行动后果。

人物：`data/characters/<id>/character.yaml`、背景与头像。
开局读取所选人物的属性、技能、资源和 `starting_equipment`；箱中物品递归读取。
标为 `owned_asset` 的资产不会放进随身物品；数量未提供时保持未知，不擅自填写数量。
人物原卡的特殊能力只是资料，只有已写入确定工具的效果才能执行。

故事：`data/campaign.json` 及 `data/scenes/`。地点、出口、NPC、物品用法和结局均来自配置。
只要机制符合现有工具，新人物和新故事可复用同一 Agent；超出现有机制的战斗或法术仍需另外开发规则工具。
修改故事会改变版本指纹；旧局明确报不兼容并保留文件，不自动改剧情或清空存档。
修正遗漏的角色初始物品时，可停服后显式执行 `scripts/sync_character_equipment.py --saves saves --investigator richard --apply`。
不加 `--apply` 只预览。脚本跳过未完成回合，修改前单独备份，不改剧情与资源，不补发已消耗或已移出的同 ID 物品。

## HTTP

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/health` | 服务状态 |
| GET | `/api/modules?page=1&page_size=3` | 故事目录、可玩标记、公开地点名单 |
| GET | `/api/modules/{module}` | 故事介绍 |
| GET | `/api/modules/{module}/cover` | 封面 |
| GET | `/api/modules/{module}/investigators` | 人物名单及可玩标记 |
| GET | `/api/modules/{module}/investigators/{person}` | 人物属性、背景、初始随身物品 |
| GET | `/api/modules/{module}/investigators/{person}/portrait` | 人物头像 |
| POST | `/api/games` | 开局：requestId、moduleId、investigatorId |
| GET | `/api/games/{game}` | 读取游戏、人物、物品、线索、对话和待恢复回合 |
| POST | `/api/games/{game}/actions` | 行动：requestId、text、expectedVersion，可选 confirmationId |
| GET | `/api/games/{game}/assets/{asset}` | 本局已允许显示的素材 |
| GET | `/api/games/{game}/review` | 结束后的复盘 |

行动返回 SSE，顺序为回合开始、进度、检定、状态更新、正文增量、完成。失败返回 `turn.failed`。
HTTP 409 表示状态、请求或确认冲突；422 表示输入不符合要求。
同一 requestId 重试必须保留原内容；恢复已提交回合不再次掷骰、发物品或扣资源。
只供查看的人物和故事即使直接调用 POST 也不能开局。

## 启动与测试

根目录运行 `python run_web.py`，或双击系统对应启动器。Python 使用 backend/.venv，依赖先按 README 安装。
网页 5175，后端 8011；用 `--no-browser` 可启动但不打开新标签。
单进程单 worker。网页存档默认 `backend/saves/`，`OWNED_WEB_SAVES` 可指定独立测试位置。
密钥放本机 `backend/.env`，不要放前端变量或提交 GitHub。
可选 `KP_MODEL_METRICS_PATH` 指定模型调用元数据文件，日志只记用量、耗时和错误分类，不记密钥或完整提示词。

离线命令见 README。真实 API 复现：

```sh
cd backend
uv run --locked python scripts/evaluate_web_live.py --live --output output/live-run-new
uv run --locked python scripts/evaluate_web_recovery_live.py --live --output output/recovery-run-new
```

第一条会占用本机 8012 端口。必须选择新的输出目录，以保留之前的失败证据；脚本不会测试新故事。
第二条用独立临时游戏进行 HTTP 检查；站台／结局补测用原故事已定义的预置进度，随机检定仍用真实系统随机数。
中断测试明确注入一次本地叙述故障，再重建服务并用真实模型恢复。它不代表供应商发生了实际网络故障。

Windows 启动器已有代码，但本轮在 macOS 执行，不能据此声称 Windows 双击启动已验证。
