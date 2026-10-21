# 项目协作约定

- 开工先读 README.md、docs/architecture.md、docs/development.md 和 docs/memory-bank/active-context.md；相关需求见 docs/design/。
- 当前源码唯一入口是 frontend/ 与 backend/，不要恢复 versions/ 下的产品副本。
- FastAPI 路由只适配 HTTP，不复制 kp_agent 的编排或 trpg 的规则。
- 当前 HTTP 仅有 GET /api/health；docs/interfaces.md 的游戏路由是待确认建议，不是已实现 API。
- 保持 backend/kp_agent、trpg、data、characters 的相对布局；调整路径必须连同 CLI、配置和测试验证。
- frontend 不得读取或打包隐藏剧情、规则原始私有内容、角色卡、模型密钥、存档。
- 现有 SQLite 是 CLI 适配，不能直接假定为多人 HTTP 服务；接游戏 API 前确认连接生命周期、线程和 game_id 隔离。
- 默认验证使用离线 demo、临时数据库和 mock；真实模型评估需明确任务授权，不能为目录迁移自动调用付费 API。
- 新工作使用独立英文主题分支；脏工作区不得自动 stash/revert。结构迁移在独立 worktree 开发。
- 后端验证：在 backend 执行 uv run --locked python -m unittest discover -s tests -t . -q。
- 前端验证：在 frontend 执行 npm ci、npm run lint、npm run typecheck、npm run build。
- 修改依赖声明必须更新对应锁文件；架构、公开接口或启动流程变化同步相关文档。
