# COC Agent＋RAG

当前主版本使用已有的 Agent＋RAG 主流程，可玩的故事包含三个地点：**旧书房 → 旧车站 → 地下档案室**。
可游玩人物仍是理查德。另有 10 位人物和《岭下暗影》的介绍及 11 个地点供查看，暂未开放游玩。
人物页显示各自的属性、背景和随身物品，包括容器说明、箱中物品、未知数量和拥有资产。
网页提供模组与角色确认、调查对话、规则出处、物品、线索、掷骰、状态、保存恢复和结案。

当前使用同一套 Agent。故事、人物、NPC 和初始物品按配置读取，不再在网页运行器里固定理查德和三个地点。
新增故事只有在接好行动条件、线索和结局并通过验证后，才应开放游玩。

## 打开

安装依赖后，macOS 可双击 `run_web.command`。Windows 使用 `run_web.bat`。
网页地址为 `http://127.0.0.1:5175`，后端端口为 `8011`。

首次在其他电脑使用时，安装 Python 3.12、uv、Node.js 24，然后分别安装依赖：

```sh
cd backend
uv sync --locked
```

```sh
cd frontend
npm ci
```

把 `backend/.env.example` 复制为同目录 `.env`，填入自己的 DeepSeek Key。
`KP_WEB_MODEL_MODE=deepseek` 使用真实模型；设为 `demo` 可使用离线关键词演示。
真实模型行动会产生 API 用量。不要把 `.env`、个人存档或依赖目录发给其他人。

## 保存

每局自动保存在当前后端的 `backend/saves/`。首页可继续最近的调查，原游戏地址也可恢复。
回复中断时点“恢复本轮”，沿用原请求，不重新掷骰或重复扣状态。
不同电脑与旧版本的存档不自动同步；网页 JSON 与 CLI SQLite 也相互独立。

## 开发入口

- `backend/kp_agent/graph.py`：原有七阶段 Agent 主流程。
- `backend/kp_agent/web.py`：复用主流程的网页适配与事件流。
- `backend/kp_agent/models.py`：同一模型适配器的行动理解、保护和流式叙述。
- `backend/kp_agent/retrieval.py`、`backend/data/agent_rules.md`：RAG 规则与出处。
- `backend/kp_agent/campaign.py`、`backend/data/campaign.json`：原三场景剧情。
- `frontend/`：网页。

当前只处理单人调查与已写明的场景规则。完整战斗、法术和多人联机不在本版范围。

## 验证与说明

- [小组文档总入口](docs/README.md)：报告材料、架构、Agent、RAG、接口、演示与历史证据。
- [报告写作材料](docs/report-guide.md)：大纲、可改写段落、实验数字和证据对应。
- [开发、接口与内容接入](docs/development.md)
- [本次测试报告](docs/evaluation/2026-10-26-test-report.md)
- [队友内容来源](docs/content-sources.md)

后端离线检查：在 `backend/` 执行 `uv run --locked python -m unittest discover -s tests -t . -q`。
前端检查：在 `frontend/` 执行 `npm ci`、`npm run lint`、`npm run typecheck`、`npm run build`。
真实 API 评估脚本必须显式加 `--live`，会产生用量；测试使用独立存档，不读取玩家存档。
