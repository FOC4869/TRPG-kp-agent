# 开发指南

## 环境和首次启动

使用 Python 3.12、uv 0.12.10、Node.js 24 LTS 和 npm。Python 目前限定 3.12 系列以维持既有基线；后续升级单独验证。
uv 安装方式见[官方说明](https://docs.astral.sh/uv/getting-started/installation/)。
以下命令在 macOS、Linux、Windows PowerShell 都可使用，不要求手动激活虚拟环境。

终端一，从仓库根目录开始：

```sh
cd backend
uv sync --locked
uv run --locked uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

终端二，从仓库根目录开始：

```sh
cd frontend
npm ci
npm run dev
```

访问 http://127.0.0.1:5173，显示桌面游戏首页。可单独运行前端预览视觉，“设置”内通过 /api/health 检查后端。
开始调查与模组库进入 #/modules，提供左右分页及公开详情。目录暂用本地示例，不请求不存在的模组 HTTP 接口；可用模组进入调查员选择页，继续调查禁用。
FastAPI 文档为 http://127.0.0.1:8000/docs。前端 5173 端口被占用会直接报错，避免无意切换端口。
需要更改后端端口时，同步调整 frontend/vite.config.ts 的代理目标。

## CLI 与模型配置

在 backend 运行：

```sh
uv run --locked python -m kp_agent --mode demo
```

模型配置使用 backend/.env；首次需要时将 backend/.env.example 复制为 backend/.env，已有文件直接编辑。
macOS/Linux 可使用 `cp -n .env.example .env`；PowerShell 使用 `if (!(Test-Path .env)) { Copy-Item .env.example .env }`。
在线模式显式执行 `uv run --locked python -m kp_agent --mode deepseek --db saves/deepseek.sqlite3`，会产生 API 用量。
不要在前端 VITE_* 变量中保存模型 key。完整说明见 model_setup.md。
backend/run_demo.command、run_deepseek.command 和对应 .bat 仍使用本目录 .venv 中的 Python；先执行 uv sync --locked。
旧 checkout 的 .venv 不可直接复制；个人 .env 与存档不自动迁移，旧故事存档也不保证跨版本兼容。

## 验证

backend：

```sh
uv sync --locked
uv run --locked python -m unittest discover -s tests -t . -q
uv run --locked python -m kp_agent --help
```

frontend：

```sh
npm ci
npm run lint
npm run typecheck
npm run build
```

后端保留原底层测试并合并 Agent 测试，测试使用 mock 或临时存档，默认不调用付费模型。
CI 执行后端离线测试、CLI 帮助和前端检查；本地增加健康接口与 Vite 代理 smoke。
Windows 启动器的真实双击行为需要 Windows 人工验证，macOS 检查不代表 Windows 已验证。
openpyxl 读取旧角色卡可能提示不支持的 Excel 扩展；导入流程只读，迁移不重写原文件。

首页布局以电脑端为主：1280×720、1440×900、1920×1080、2560×1080；短窗口可纵向滚动，窄屏保留基本可用性。
视觉验收包括背景裁切、按钮可见性、弹窗关闭与焦点恢复、键盘操作、减少动态效果及连接失败/重试。
首页范围与素材来源见 docs/design 下的 homepage 文档及 frontend/public/images/README.md。

模组库同样以桌面为主，窄屏下详情移至列表下方。验收每页 3 项、末页 1 项、首尾按钮禁用、卡片与详情同步、翻页焦点、返回首页/浏览器返回/刷新；仅《岭下暗影》展示用户提供的公开引言。示例条目见 frontend/src/data/modules.ts；日后接 HTTP 时替换 api/modules.ts 并同步接口契约。

## 预设调查员数据

预设调查员数据位于 backend/data/characters/<id>/，每位包含 character.yaml、background.md、assets/portrait.png。字段、原卡疑点和附件引用约定见 backend/data/characters/README.md。新增角色不需要注册 manifest；未来加载器按角色文件扫描。当前未接入 CLI 或网页，不根据新数据改变原有角色加载流程。

前端选择页 `#/investigators?module=darkness-beneath-the-hill` 当前使用独立假资料与原创假头像，并未读取上述后端目录。
列表/详情通过 api/investigators.ts，显示类型在 types/investigators.ts；页面不直接导入 mock。接入指南见 [调查员 API 适配契约](investigator-api.md)。
验收十张卡片、四标签及键盘左右/Home/End、未知字段、确认/Escape、快速切换、刷新/返回和无效模组；首次无选择时确认禁用。桌面主视口为 1280×720、1440×900、1920×1080 和宽屏；档案面板高度随视口调整，长内容在标签面板内滚动，确认按钮保持可见，切换标签不改变整页高度。

## 依赖更新

后端声明为 pyproject.toml，解析结果为 uv.lock；`uv add <package>` / `uv add --dev <package>` 后提交两者。
安装使用 `uv sync --locked`，禁止为消除报错而顺手升级模型 SDK。历史 requirements 保存在 docs/history，只作来源证据。
前端使用 `npm install <package>` / `npm install -D <package>`，提交 package.json 和 package-lock.json；安装使用 npm ci。
本轮前端来源命令为 `npm create vite@latest frontend -- --template react-ts --no-interactive`，create-vite 9.3.1。

## 分支、变更与目录

使用英文主题分支，如 chore/standardize-project-structure；团队尚未约定统一前缀，本例不改变其他分支流程。
新 feature 或跨目录迁移从干净目标提交建立分支，优先独立 worktree。不得自动 stash/revert 他人未提交内容。
只在 frontend/backend 维护当前源码；旧发布链接仅作指引。新接口先更新契约，路由保持薄层。
架构或边界变化记入 docs/decisions；影响开发入口的变更同步 README 和本指南。

参考：[Vite 初始化](https://vite.dev/guide/)、[FastAPI 入口](https://fastapi.tiangolo.com/tutorial/first-steps/)、[uv 项目文件](https://docs.astral.sh/uv/concepts/projects/layout/)。
