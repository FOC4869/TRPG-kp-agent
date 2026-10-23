# TRPG AI KP

基于 Vite、React、FastAPI 和 LangGraph 的 AI 守秘人项目。当前已完成的业务主体是 LangGraph Agent、RAG 和角色／骰子工具；网页已实现桌面首页、分页模组库／详情和假数据调查员选择页，游戏页面与 HTTP 接口待接入。

## 从哪里开始

| 目录 | 职责 |
|---|---|
| `frontend/` | Vite + React + TypeScript；首页、模组库／详情、调查员选择与设置面板 |
| `backend/app/` | FastAPI HTTP 适配；当前仅实现 `GET /api/health` |
| `backend/kp_agent/` | LangGraph 行动编排、RAG、场景、模型和现有存储适配 |
| `backend/trpg/` | 唯一的角色、骰子、检定与规则实现 |
| `backend/data/`、`backend/characters/` | 后端规则资料、剧情配置和角色卡 |
| `backend/data/characters/` | 十位预设调查员的 YAML、背景正文与头像；格式见目录 README，尚未接入游戏 |
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

打开 <http://127.0.0.1:5173>。首页与模组库可以在不启动后端时浏览；“开始调查”进入每页 3 项的模组库，点击卡片切换右侧详情。“继续调查”灰显禁用，本轮不实现存档。
模组库直达地址为 <http://127.0.0.1:5173/#/modules>。当前使用前端示例目录：《岭下暗影》的公开引言与 6 条待收录占位记录，用于展示 3／3／1 翻页。
选择《岭下暗影》后进入调查员页：十人照片墙、概览/属性技能/背景/物品四标签及确认弹窗。人物资料和头像均为独立假数据/假资源，未加载后端原卡。确认只显示准备信息，不创建游戏/存档；[API 适配契约](docs/investigator-api.md)描述后续接入点。
设置面板提供减少动态效果和按需连接检查。Vite 会把 `/api` 转发至本地后端；接口文档位于 <http://127.0.0.1:8000/docs>。
健康检查不加载模型或玩家存档，不会产生模型费用。连接成功代表健康接口可达。

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

《岭下暗影》的完整正文、结构化资料和附件见[模组内容包](backend/data/modules/darkness-beneath-the-hill/README.md)。当前用于内容审阅，尚未接入 CLI 或网页游戏。
