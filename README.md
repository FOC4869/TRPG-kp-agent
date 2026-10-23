# TRPG AI KP

基于 Vite、React、FastAPI 和 LangGraph 的 AI 守秘人项目。当前已完成的业务主体是 LangGraph Agent、RAG 和角色／骰子工具；网页已实现桌面首页及分页模组库／详情，游戏页面与 HTTP 接口待接入。

## 从哪里开始

| 目录 | 职责 |
|---|---|
| `frontend/` | Vite + React + TypeScript；桌面首页、分页模组库／详情与设置面板 |
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
模组库直达地址为 <http://127.0.0.1:5173/#/modules>。当前使用前端示例目录：《岭下暗影》的公开引言与 6 条待收录占位记录，用于展示 3／3／1 翻页。调查员选择目前只显示尚未开放提示。
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

## 可安装的角色卡导入 Skill

[coc-character-card-import](skills/coc-character-card-import/SKILL.md) 把单张或批量 CoC 角色卡图片转为 character.yaml、background.md 和裁切头像。格式说明、虚构示例与脚本均在技能目录内，不需要本项目代码或历史对话。Python 辅助脚本使用 Pillow、PyYAML，依赖在独立环境安装，不修改使用者的项目。

技能位于标准的 `skills/<name>/SKILL.md` 布局，可由 [skills CLI](https://github.com/vercel-labs/skills) 发现。发布到 GitHub 默认分支后，任何有仓库读取权限的人可以运行：

```sh
npx skills add FOC4869/TRPG-kp-agent
# 仓库有多个技能时，可明确指定：
npx skills add FOC4869/TRPG-kp-agent --skill coc-character-card-import
```

若仅发布在其他分支，需用该分支的 GitHub tree URL 作为来源；不能假定默认分支已经有此技能。安装器选择目标 agent、项目/全局范围；需要普通文件副本时加 `--copy`。只安装技能目录，不需要安装本项目后端/前端。安装后向支持技能的 agent 提供角色卡图片和输出目录，例如：

```text
使用 $coc-character-card-import，把这些角色卡导入到 ./data/characters。
```

本地开发可在目标项目中执行 `npx skills add /path/to/TRPG-kp-agent --skill coc-character-card-import --agent codex --copy`。个人 Codex 目录也可复制完整技能到 `$CODEX_HOME/skills/coc-character-card-import`（未设置 CODEX_HOME 时为 `~/.codex/skills/coc-character-card-import`）；已有目录时先处理冲突，不覆盖。仓库中的技能是维护源，安装副本不独立修改。
