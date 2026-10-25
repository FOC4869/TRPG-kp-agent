# COC Agent＋RAG 网页副本

这份副本使用已有的 Agent＋RAG 主流程，保留原来的三个地点：**旧书房 → 旧车站 → 地下档案室**。
角色继续使用原来的理查德角色卡。网页提供模组与角色确认、调查对话、规则出处、物品、线索、掷骰、状态、保存恢复和结案。

## 打开

当前电脑可双击 `run_web.command`。Windows 使用 `run_web.bat`。
网页地址为 `http://127.0.0.1:5175`，后端端口为 `8011`。

首次在其他电脑使用时，安装 Python 3.12、uv、Node.js，然后分别安装依赖：

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

每局自动保存在本副本的 `backend/saves/`。首页可继续最近的调查，原游戏地址也可恢复。
回复中断时点“恢复本轮”，沿用原请求，不重新掷骰或重复扣状态。
这份副本使用独立存档，不读取原项目的游玩记录。

## 开发入口

- `backend/kp_agent/graph.py`：原有七阶段 Agent 主流程。
- `backend/kp_agent/web.py`：复用主流程的网页适配与事件流。
- `backend/kp_agent/models.py`：同一模型适配器的行动理解、保护和流式叙述。
- `backend/kp_agent/retrieval.py`、`data/agent_rules.md`：RAG 规则与出处。
- `backend/kp_agent/campaign.py`、`data/campaign.json`：原三场景剧情。
- `frontend/`：网页。

当前只处理单人调查与已写明的场景规则。完整战斗、法术和多人联机不在本版范围。
