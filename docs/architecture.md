# 当前架构

项目采用 frontend/backend 单仓布局。技术栈由用户确定为 Vite + React + FastAPI + LangGraph。
本文件是当前目录与边界的说明；原始产品设计保留在 history/foundation-design.md，Agent 专题设计见 agent-design.md。

## 运行链路

当前网页提供桌面首页、分页模组库／公开详情、假数据调查员选择与设置弹窗。这些页面独立于后端；打开设置时执行 React → Vite 的 /api 开发代理 → FastAPI GET /api/health。
开始调查进入 #/modules；卡片选择更新详情，每页最多 3 项。可用模组进入 #/investigators?module=<id>，确认调查员显示案件/人物摘要，不创建游戏。继续调查禁用；网页不读写存档。
frontend/src/api/modules.ts 是前端分页适配入口，目前从 data/modules.ts 的明确示例目录读取，不请求后端。PublicModule 只允许公开的目录资料；后续确认 GET 契约后替换读取实现，不把守秘人信息传给前端。7 条示例包含《岭下暗影》和 6 条待收录记录；真实接入时按后端 total/items 渲染，末页不补占位项。
调查员展示类型在 frontend/src/types/investigators.ts，api/investigators.ts 分开读取摘要与详情，当前仅访问 data/investigators.ts 的独立 mock。请求传 moduleId/AbortSignal，切换或卸载取消旧请求；不复制后端人物数据和头像。未来适配 HTTP 返回授权资料及头像 URL，不要求页面理解 YAML 或后端路径，详见 [调查员适配契约](investigator-api.md)。
当前游戏链路是 CLI → KeeperService → LangGraph → 场景校验、RAG、trpg 和 SQLite 适配。
两条链路尚未连接成网页游戏。健康接口只表明进程可响应，不检查模型配置、剧情或数据库。

未来游戏 HTTP 层调用现有 KeeperService，路由只负责请求校验、错误映射与资源生命周期。
业务规则、骰子、状态提交仍由后端处理。interfaces.md 中的游戏 HTTP 地址仍为建议。

## 目录与数据归属

- frontend/src：React UI、api 请求封装、styles；不放秘密剧情或模型凭据。
- frontend/public/images：原创生成的首页背景、地窖封面及独立假头像图集。标题、导航与按钮由 HTML/CSS 实现，不以整张生图替代交互；完整提示词位于 docs/design/image-assets.md，不随 public 分发。
- backend/app：FastAPI 入口和路由。导入应用不初始化 Agent、模型或存档。
- backend/kp_agent：现有 LangGraph 流程、模型、检索、场景和存储适配。保留包名与相对路径。
- backend/trpg：角色、骰子和规则的唯一实现。迁移采用原发布子目录后续实现。
- backend/data 与 characters：服务端输入资产，不作为 FastAPI 静态目录公开。
- backend/data/characters/<id>：新增预设调查员的 YAML、Markdown 与头像，按 ID 独立组织，无 manifest；格式见该目录 README。模板与游戏存档分开，目前未接入运行时。旧 backend/characters 下的 Excel 路径保留。
- backend/saves 与 output：本地状态与生成结果，Git 忽略。
- docs/evaluation 与 history：归档的评估和历史依据，不作为运行输入。
- skills/coc-character-card-import：可独立安装的 CoC 角色卡导入技能；自带格式说明和辅助脚本，不导入游戏实现，不属于运行时链路。

当前 Agent 通过现有 SQLite 适配统一保存角色与剧情。它是本地单玩家演示，不是已完成的多人数据库方案。
接 HTTP 游戏接口前必须明确 SQLite 连接的线程归属、KeeperService 生命周期、请求并发、game_id 隔离和关闭流程，不能直接把一个 CLI 实例放进任意线程池。

## 工程决定

- Python 3.12，uv 管理依赖与 backend/.venv；npm 管理独立前端依赖。
- LangGraph、OpenAI SDK、Pydantic、dotenv 和 openpyxl 保持原发布基线；新增 FastAPI/uvicorn/httpx 用于 HTTP 骨架及测试。
- 开发仅监听回环地址。Vite 将 /api 代理至 127.0.0.1:8000；不需要为本地代理开启通配 CORS。
- 生产构建只含前端资产；将来的部署需要同源 /api 反向代理，vite preview 不提供开发代理保证。
- 暂不引入共享包、任务编排框架、前端状态库、ORM 或部署平台。出现实际需求再做决定。

目录迁移的决定与替代方案见 [ADR-0001](decisions/ADR-0001-project-layout.md)。

## 模组内容包

仓库 skills/coc-module-builder 是可单独分发的制作工具，包含格式说明、原创模板、视觉扩展约定和只读校验器；不依赖 kp_agent/trpg，也不加载存档或启动 HTTP。视觉扩展单独版本化，不迁移现有模组。实际展示授权、素材 API 与游戏执行器仍需另行实现。

`backend/data/modules/darkness-beneath-the-hill/` 保存《岭下暗影》完整正文、YAML 提取资料与统一附件索引。它是服务端内容包草案，尚未接入现有 `CampaignDefinition` JSON 加载器或 KeeperService。素材分类依靠索引，不要求固定类型目录；默认不对玩家开放。见 [ADR-0002](decisions/ADR-0002-module-content-package.md) 和[包说明](../backend/data/modules/darkness-beneath-the-hill/README.md)。
