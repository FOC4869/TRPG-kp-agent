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

访问 http://127.0.0.1:5173，显示桌面游戏首页。可单独运行前端预览视觉，开发时通过 /api/health 检查后端。
开始调查与模组库进入 #/modules，提供左右分页及公开详情。目录与人物页需要启动后端，使用真实只读 HTTP；可用模组进入调查员选择页，首页继续调查会校验本浏览器最近游戏，游戏也可通过自身URL恢复。
FastAPI 文档为 http://127.0.0.1:8000/docs。前端 5173 端口被占用会直接报错，避免无意切换端口。
需要更改后端端口时，同步调整 frontend/vite.config.ts 的代理目标。

## 网页游戏

网页行动需要backend/.env中配置DEEPSEEK_API_KEY；模型默认deepseek-flash、关闭思考。密钥不放VITE变量，不提交.env。目录与健康离线可用，游戏行动未配置模型时明确失败，保留原请求供配置后恢复。

POST创建成功后进入#/game?game=<id>；每局自动保存到saves/<id>/game.json。根目录进程锁只允许一个运行器进程／worker，启动时不要加--workers 2；开发--reload会在旧worker退出后释放锁。WEB_GAME_SAVES可选指定独立保存根目录，避免与另一个开发进程冲突。网页服务保留至应用退出才关闭模型与存储。

离线测试使用fake Agent和临时目录，不消耗模型。显式付费评估：`uv run --locked python scripts/evaluate_web_mvp.py --live`，稳定请求／游戏可恢复，指标位于output/web-mvp-evaluation/report.json；脚本最多90请求，为浏览器等额外测试预留会话总120请求预算。不要删除报告后重复跑来绕开总预算。完整规则与多人上线不在当前范围。

首页继续调查只保存localStorage键`coc:last-active-game`，值为game_id；同源、同浏览器生效。此前已有的存档用原游戏地址打开一次后会记住。结案完整落盘或明确404时清除相同编号；中断最终叙述仍保留入口。网络／损坏／版本错误保留编号，允许重新检查，不扫描服务端存档。测试清除此键不会删除后端存档。

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
node scripts/check-recent-game.mjs # 编号、活动／未决／终局、404／故障、取消与浏览器存储边界
node scripts/check-catalogue.mjs
node scripts/check-game-preview.mjs # 当前验证真实SSE适配器的离线拆块／去重／断流
```

后端保留原底层测试并合并 Agent 测试，测试使用 mock 或临时存档，默认不调用付费模型。
当前未配置 CI。提交前在本地手动执行上述后端离线测试、CLI 帮助和前端检查；涉及接口或启动流程时增加健康接口与 Vite 代理 smoke。
Windows 启动器的真实双击行为需要 Windows 人工验证，macOS 检查不代表 Windows 已验证。
openpyxl 读取旧角色卡可能提示不支持的 Excel 扩展；导入流程只读，迁移不重写原文件。

首页布局以电脑端为主：1280×720、1440×900、1920×1080、2560×1080；短窗口可纵向滚动，窄屏保留基本可用性。
视觉验收包括背景裁切、按钮可见性、弹窗关闭与焦点恢复、键盘操作、减少动态效果及连接失败/重试。
首页范围与素材来源见 docs/design 下的 homepage 文档及 frontend/public/images/README.md。

模组库同样以桌面为主，窄屏下详情移至列表下方。验收每页最多 3 项、末页不补空卡、首尾按钮禁用、卡片与详情同步、翻页焦点、返回首页/浏览器返回/刷新；仅《岭下暗影》展示用户提供的公开引言。发布清单见 backend/data/module-catalogue.json；当前仅一条真实模组，3／3／1 分页使用后端临时七项清单测试。

## 预设调查员数据

预设调查员数据位于 backend/data/characters/<id>/，每位包含 character.yaml、background.md、assets/portrait.png。字段、原卡疑点和附件引用约定见 backend/data/characters/README.md。新增角色不需要独立 manifest；网页发布需要在 module-catalogue.json 的 investigatorIds 登记。当前已接网页选择页，CLI 仍使用原有角色加载流程。

前端选择页 `#/investigators?module=darkness-beneath-the-hill` 通过 HTTP 获取上述目录的公开资料和限定头像 URL；不直接导入后端文件。
列表/详情通过 api/investigators.ts，显示类型在 types/investigators.ts；页面不直接导入 mock。接入指南见 [调查员 API 适配契约](investigator-api.md)。
验收十张卡片、四标签及键盘左右/Home/End、未知字段、确认/Escape、快速切换、刷新/返回和无效模组；首次无选择时确认禁用。桌面主视口为 1280×720、1440×900、1920×1080 和宽屏；档案面板高度随视口调整，长内容在标签面板内滚动，确认按钮保持可见，切换标签不改变整页高度。

## 依赖更新

模组制作 skill 在 skills/coc-module-builder，自包含分发，入口见其 SKILL.md。独立检查：

~~~sh
uv run --locked --script skills/coc-module-builder/scripts/validate_module.py --self-test
uv run --locked --script skills/coc-module-builder/scripts/validate_module.py <module-dir> --resume --json
~~~

首次运行 uv 会准备隔离的 Python/PyYAML/Pillow 环境；脚本依赖由自身 PEP 723 声明及 validate_module.py.lock 锁定，与 backend/uv.lock 无关。校验是只读操作，默认允许未生成图片的草案，--complete 要求全部计划验收且指纹一致，均不证明模组可运行。旧包缺视觉扩展或原始来源时仅报告，不自动迁移。无代码/依赖运行时变更的 skill 交付运行自身测试即可，不需要前端浏览器检查。

后端声明为 pyproject.toml，解析结果为 uv.lock；`uv add <package>` / `uv add --dev <package>` 后提交两者。
安装使用 `uv sync --locked`，禁止为消除报错而顺手升级模型 SDK。历史 requirements 保存在 docs/history，只作来源证据。
前端使用 `npm install <package>` / `npm install -D <package>`，提交 package.json 和 package-lock.json；安装使用 npm ci。
本轮前端来源命令为 `npm create vite@latest frontend -- --template react-ts --no-interactive`，create-vite 9.3.1。

## 仓库文件与生成产物

根 `.gitignore` 覆盖前后端与独立 skills 的虚拟环境、依赖和工具缓存；本地 `.env` 与 `*.local` 不提交，`.env.example`／`.env.*.example` 模板保留。
玩家存档与模型调用日志放在 `backend/saves/`；评估脚本默认从 backend 执行，输出放在 `backend/output/`，仓库级 QA 使用根 `output/`。临时日志使用根或 backend 下的 `logs/`。
前端构建与覆盖率输出使用 `frontend/dist/`、`frontend/coverage/`。这些目录均忽略；需要保留的评估证据先审阅，再放入 `docs/evaluation/`。
不按扩展名统一忽略 JSONL、ZIP 或日志：模组附件、测试样本与已审阅报告可按实际需要提交。`backend/uv.lock`、前端 package-lock 和 skill 的脚本锁文件必须保留。
`.gitattributes` 固定源码为 LF、Windows `.bat` 为 CRLF，二进制素材禁止文本转换；`.editorconfig` 与这些换行约定保持一致。

## 分支、变更与目录

使用英文主题分支，如 chore/standardize-project-structure；团队尚未约定统一前缀，本例不改变其他分支流程。
新 feature 或跨目录迁移从干净目标提交建立分支，优先独立 worktree。不得自动 stash/revert 他人未提交内容。
只在 frontend/backend 维护当前源码；旧发布链接仅作指引。新接口先更新契约，路由保持薄层。
架构或边界变化记入 docs/decisions；影响开发入口的变更同步 README 和本指南。

参考：[Vite 初始化](https://vite.dev/guide/)、[FastAPI 入口](https://fastapi.tiangolo.com/tutorial/first-steps/)、[uv 项目文件](https://docs.astral.sh/uv/concepts/projects/layout/)。

## 游戏主界面验证

从调查员确认创建真实游戏。桌面验收独立背景／立绘、发送／等待／建议、内部滚动、人物／背包／线索／记录抽屉、中文输入、检定顺序、断线／刷新／重启恢复、无NPC场景和结案。SSE字节拆分等由离线脚本验证，模型与桌面证据见evaluation/playable-mvp.md。
真实结束条件由运行器执行。验收最终正文保存后弹窗、关闭/Escape后输入不恢复、“查看结案”重开和返回首页；长总结内部滚动，窄屏／短屏保留返回按钮。

公开目录服务与发布步骤见 [目录 HTTP 契约](catalogue-api.md)。适配 smoke 需要先准备 backend/.venv；默认只用真实公开投影及测试端 HTTP mock，不调用模型。
