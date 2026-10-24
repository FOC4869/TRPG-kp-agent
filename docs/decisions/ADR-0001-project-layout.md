# ADR-0001：采用 frontend/backend 单仓结构

状态：已接受（用户于 2026-10-21 确认）。

## 背景

根目录保留最初 trpg 与测试，versions/ai-kp-v1 则是在其基础上发展的完整 Agent/RAG 后续实现；两份底层已有差异。
项目后续技术栈确定为 Vite React + FastAPI + LangGraph，需要给前后端组员提供清晰开发边界。

## 决定

- frontend 为 Vite 官方 React TypeScript 模板，使用 npm 独立锁文件。
- backend 容纳 app（HTTP）、kp_agent（LangGraph）、trpg（底层）、数据和全部后端测试，使用 uv 独立锁文件。
- 以 7aa25aa 中发布子目录的产品文件为基础，保留根目录旧测试；不同时重构包名或模块。
- 原设计、来源快照和依赖清单归档 docs/history，评估证据保留 docs/evaluation；旧发布目录保留迁移指引。
- 第一阶段 HTTP 仅实现无模型、无存档副作用的 /api/health，不承诺游戏接口或多人能力。

## 替代方案与代价

继续维护 versions 副本会延续双份修复与错误导入；全部放仓库根目录不满足用户明确的 backend 边界。
采用 apps/services/shared packages 会增加当前三人项目的层级，暂不需要。
迁移会改变旧启动目录和文档路径，因此同步更新指引、测试与 CI。原始发布版仍可从 Git 7aa25aa 获取。

未来新增游戏 HTTP 接口时另记服务生命周期、数据库并发与请求隔离的决定。
