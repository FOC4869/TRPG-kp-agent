# 前后端工程初始化

状态：已完成。日期：2026-10-21。依据：用户确认采用 frontend/backend 结构，并授权在新英文分支执行。

## 目标与边界

将两套 Python 源码收敛到 backend，保留现有 Agent CLI 与底层能力；建立 Vite + React + TypeScript 前端、FastAPI 健康接口、独立依赖锁和 CI。
本次不增加游戏 HTTP 接口、聊天页面、鉴权、多人状态或新数据库，不修改模型提示词及剧情。

## 架构决定

- frontend 只包含浏览器代码，backend/app 是 HTTP 适配层，backend/kp_agent 是 LangGraph 业务编排，backend/trpg 是底层规则。
- 保留 kp_agent、trpg、data、characters 的相对布局。暂不改成 src 布局或拆分大模块。
- 以 7aa25aa 的 versions/ai-kp-v1 后续实现为迁移基础；根目录旧测试合并，预期冲突单独记录。
- Python 使用 pyproject.toml + uv.lock；前端使用 npm + package-lock.json。秘密、存档、缓存和构建结果忽略。
- 当前开发分支 chore/standardize-project-structure 使用本聊天已附加的独立 worktree，原 taosdev checkout 保留。

## 切片与验证

1. 源码和证据迁移：产品业务逻辑/data/角色卡保持原内容，仅更新过时安装提示；旧底层测试纳入 backend/tests，运行全部 unittest。已知成长上限旧断言与后续规则冲突，依据后续规则语料与实现核对。
2. 骨架：backend/app/main.py 与 api/health.py 提供 GET /api/health；frontend 提供健康状态页和同源请求封装，Vite 开发代理转发 /api。运行健康接口测试、类型检查和构建。
3. 开发入口：根 README/AGENTS、docs/architecture.md/development.md、迁移记录、Git 忽略规则和 CI。核对 CLI --help、离线 demo、链接与路径、git diff --check。

## 文件边界和评审

- backend：现有产品代码、单元测试、配置模板、依赖与 CLI 脚本。
- frontend：最小 React 工程，不放剧情数据或密钥。
- docs：当前架构/接口/开发指南与历史、评估证据。历史文件标明旧路径上下文。
- .github/workflows/ci.yml：后端离线测试和前端类型检查/构建，不调用付费模型。
- 评审按架构、开发体验、代码和 QA 顺序在本会话完成；无需并行 agent。

## 迁移与回退

历史源码可从 7aa25aa 及之前提交恢复；versions/ai-kp-v1 仅保留迁移指引。原始评估与来源快照归档，不重新声称本次运行了真实模型或 Windows 验证。
不搬运个人 .env、虚拟环境或存档。回退可在提交后 revert 本次结构变更，不需要数据库迁移。

## 验收结果

后端 191 项离线测试通过；CLI demo 与相同消息重试通过；FastAPI 健康接口及 Vite /api 代理实测通过；前端 lint、类型检查和生产构建通过。依赖锁安装、当前文档链接与忽略规则已检查。Windows 由 CI 配置覆盖，尚未在本地真实 Windows 或远端 CI 执行；本次未调用付费模型、未做正式游戏网页联调。
