# TRPG AI KP

基于 Vite、React、FastAPI、LangGraph 与 DeepSeek 的单人 AI 守秘人。已接通真实目录、十位调查员、创建与恢复、自然语言行动、自动检定、流式叙述和游戏内结案。当前正式发布《岭下暗影》的独立单人简化改编；通用运行器支持通过结构化配置接入使用现有机制的新模组。

## 从哪里开始

| 目录 | 职责 |
|---|---|
| `frontend/` | Vite + React + TypeScript；首页、模组库／详情、调查员选择、可游玩游戏页 |
| `backend/app/` | FastAPI HTTP 适配；健康、目录及游戏 HTTP／SSE |
| `backend/kp_agent/` | LangGraph 行动编排、RAG、场景、模型和现有存储适配 |
| `backend/trpg/` | 唯一的角色、骰子、检定与规则实现 |
| `backend/data/`、`backend/characters/` | 后端规则资料、剧情配置和角色卡 |
| `backend/data/characters/` | 十位预设调查员的 YAML、背景正文与头像；格式见目录 README，已接选择页和游戏实例快照 |
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

打开 <http://127.0.0.1:5173>，从模组库选择《岭下暗影》和调查员，点击“开始调查”创建真实游戏。网页游戏使用 `backend/.env` 的 `DEEPSEEK_API_KEY` 与可选 `DEEPSEEK_MODEL=deepseek-flash`；密钥只放后端，正常每轮最多两次付费模型调用。健康与只读目录不调用模型。

游戏地址为 `#/game?game=<game_id>`，刷新或重启后可恢复；每局自动保存到 `backend/saves/<game_id>/game.json`。首页“继续调查”会恢复本浏览器最近打开的未结案游戏；浏览器只记编号，不保存完整游戏内容，不提供存档管理列表。只允许一个后端进程／worker，运行器会检查进程锁；本地监听回环地址。

自由输入后通过 SSE 依次展示自动 D100 检定、实际 HP／SAN 与物品／线索变化、独立伤害卡、流式 Keeper 正文。新局使用十一场景调查扩充版：城内查档、河墙备用出口、壁画／音乐室／巢窟、陷坑和牢笼。线索提供替代方法与结案证据，保留立即同行和次日失踪两条乔什路线；已有存档继续原配置；游戏内结案弹窗复用最终正文。持有物品可照明、取放或交给在场NPC；危险动作先确认后结算，新局工具箱演示目标技能与工具交互。网络失败用原请求恢复，不静默切换假回复。复杂 CoC 规则暂未实现。

Vite 将 `/api` 转发至本地8000；接口文档 <http://127.0.0.1:8000/docs>，契约见 [HTTP／SSE](docs/interfaces.md)，范围与验证见 [MVP](docs/design/done/simplified-mvp.md) 和 [评估](docs/evaluation/playable-mvp.md)。

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

- [MVP冻结基线（2026-10-24）](docs/releases/mvp-freeze-2026-10-24.md)
- [架构与边界](docs/architecture.md)
- [开发指南](docs/development.md)
- [可游玩单人 MVP](docs/design/done/simplified-mvp.md)
- [当前用户旅程](docs/user-journey.md)
- [模组存储结构](docs/module-storage.md)
- [模组运行配置与接入](docs/runtime-profiles.md)
- [人物存储结构](docs/character-storage.md)
- [已有 Agent 能力及 CLI](docs/agent-guide.md)
- [已实现的公开目录 HTTP](docs/catalogue-api.md)
- [网页游戏 HTTP／SSE 契约](docs/interfaces.md)
- [结构迁移记录](docs/history/structure-migration.md)

## 可安装的模组制作 skill

[coc-module-builder](skills/coc-module-builder/SKILL.md) 自带内容格式、模板、统一画风流程和独立校验器，不依赖聊天记录或项目运行时。默认整理模组、规划素材并制作首批样本；此交付未修改现有模组或生成新素材。

从本仓库本地安装：`npx skills add . --skill coc-module-builder`。发布到远端可访问分支后可使用 `npx skills add FOC4869/TRPG-kp-agent --skill coc-module-builder`；尚未发布的版本不能通过默认远端安装获得。

离线验证：`uv run --locked --script skills/coc-module-builder/scripts/validate_module.py --self-test`。依赖和锁文件仅属于该 skill，不改变后端或前端依赖。制作输出仍是声明式草案，不等于已接入游戏。

《岭下暗影》的完整正文、结构化资料和附件见[模组内容包](backend/data/modules/darkness-beneath-the-hill/README.md)。完整包用于内容审阅，网页运行器另以独立单人简化配置引用其中场景与素材，不宣称完整包全部可执行。

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
