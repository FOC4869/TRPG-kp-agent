# 当前上下文

2026-10-22：chore/standardize-project-structure 已快进合并到 taosdev；当前 design/frontend-ui 分支实现桌面首页。
用户确认首页 → 模组库/详情 → 选择调查员 → 游戏（Galgame 对话）→ 结案的五页旅程。本轮仅做首页，存档/继续调查暂不实现并灰显。
首页采用原创生成的雨夜旧宅背景；标题、导航与按钮均为 HTML/CSS，兼顾电脑宽屏与短窗口。开始调查打开公开模组预览，设置含减少动态效果及按需健康检查。尚无游戏 HTTP、角色选择或完整模组页面。
前端依赖未增加；素材及最终提示词保存在 frontend/public/images/README.md。后端与原 CLI 存档机制未改。
验证：npm ci/lint/typecheck/build 通过；浏览器已检查桌面/宽屏/短屏/窄屏、弹窗和连接失败重试。首页记录见 docs/design/done/homepage.md。
下一步：按既定旅程设计模组库/详情；接游戏 HTTP 前仍需确认 KeeperService/SQLite 生命周期与请求隔离。

以下为初始化历史：

2026-10-21：用户确认将项目初始化为 frontend（Vite React TypeScript）与 backend（FastAPI + 现有 LangGraph），在英文分支 chore/standardize-project-structure 实施。

源码从 7aa25aa 的 versions/ai-kp-v1 整体迁至 backend，根目录底层测试合并；底层与 Agent 均只有一份当前实现。前端由 Vite 官方命令生成。
HTTP 只提供 GET /api/health；React 页面用于检查连接。游戏接口、聊天页面、多人会话和数据库替换未实现。
依赖与启动以 README/development 为准。个人秘密、存档和虚拟环境不迁移。

下一步：在游戏 HTTP 接口实现前确认 KeeperService/SQLite 生命周期与请求隔离，更新接口契约；前端产品界面按实际需求另行设计。
目录迁移决策见 ADR-0001，路径和规则测试冲突见 history/structure-migration.md。

验证：191 项后端离线测试通过；CLI demo/重试、健康接口与 Vite 代理通过；前端 lint/typecheck/build 通过。未调用付费 API，未在本地运行 Windows 或远端 CI。完整初始化记录见 docs/design/done/project-bootstrap.md。
