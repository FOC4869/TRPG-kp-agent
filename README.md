# TRPG AI KP

基于 Vite、React、FastAPI 和 LangGraph 的 AI 守秘人项目。当前已完成的业务主体是 LangGraph Agent、RAG 和角色／骰子工具；网页处于工程骨架阶段。

## 从哪里开始

| 目录 | 职责 |
|---|---|
| `frontend/` | Vite + React + TypeScript；当前仅提供后端连接状态页 |
| `backend/app/` | FastAPI HTTP 适配；当前仅实现 `GET /api/health` |
| `backend/kp_agent/` | LangGraph 行动编排、RAG、场景、模型和现有存储适配 |
| `backend/trpg/` | 唯一的角色、骰子、检定与规则实现 |
| `backend/data/`、`backend/characters/` | 后端规则资料、剧情配置和角色卡 |
| `backend/tests/`、`backend/scripts/` | 统一后端测试和评估脚本 |
| `docs/` | 架构、开发、接口说明、评估及历史证据 |
| `versions/ai-kp-v1/` | 旧链接迁移指引，不再维护源码 |

## 本地运行

准备 Python 3.12、[uv](https://docs.astral.sh/uv/getting-started/installation/)、Node.js 24 LTS 和 npm。以下命令均从仓库根目录开始，两端分别使用一个终端。

后端：

```sh
cd backend
uv sync --locked
uv run --locked uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

前端：

```sh
cd frontend
npm ci
npm run dev
```

打开 <http://127.0.0.1:5173>。Vite 会把 `/api` 转发至本地后端；接口文档位于 <http://127.0.0.1:8000/docs>。
健康检查不加载模型或玩家存档，不会产生模型费用。连接成功代表前后端健康接口可达，游戏网页接口尚未接入。

现有离线 Agent CLI：

```sh
cd backend
uv run --locked python -m kp_agent --mode demo
```

`demo` 是离线关键词规划；真实模型需在 `backend/.env` 显式配置并选择在线模式，见[模型配置](docs/model_setup.md)。CLI 仍支持 backend 下的 `.command` 和 `.bat` 启动器。

## 检查与协作

```sh
cd backend
uv run --locked python -m unittest discover -s tests -t . -q
```

```sh
cd frontend
npm run lint
npm run typecheck
npm run build
```

依赖分别以 `backend/pyproject.toml` + `backend/uv.lock`、`frontend/package.json` + `frontend/package-lock.json` 为准。
不要提交 `.env`、虚拟环境、`node_modules`、玩家存档或构建产物；不要把后端剧情和密钥复制到前端。

- [架构与边界](docs/architecture.md)
- [开发指南](docs/development.md)
- [已有 Agent 能力及 CLI](docs/agent-guide.md)
- [Python 接口及待接入 HTTP 契约](docs/interfaces.md)
- [结构迁移记录](docs/history/structure-migration.md)
