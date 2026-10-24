# 项目协作约定

本文件只保留协作规则；功能现状、接口和实施历史由链接文档维护。

## 阅读入口

- 开工阅读 [README](README.md)、[架构](docs/architecture.md)、[开发指南](docs/development.md) 和 [当前上下文](docs/memory-bank/active-context.md) 顶部结论；历史记录按需查阅。
- 需求与验收见 `docs/design/`；目录契约见 [catalogue-api](docs/catalogue-api.md)，游戏与 SSE 契约见 [interfaces](docs/interfaces.md)，模组接入见 [runtime-profiles](docs/runtime-profiles.md)。

## 代码与数据边界

- 产品源码位于 `frontend/` 和 `backend/`；`skills/` 是独立内容制作工具，不恢复 `versions/` 下的产品副本。
- FastAPI 只适配 HTTP、错误和生命周期；编排与状态提交在 `backend/kp_agent/gameplay/`，规则计算在 `backend/trpg/`。LLM 不能直接修改资源或存档。
- 模组差异通过内容与运行配置表达；已有通用能力支持的新模组不增加按模组名或 NPC 名分支的 Python 逻辑。新增机制先明确并验证通用工具契约。
- 前端只消费公开 API 投影与按局授权素材；不得直接读取、打包或静态暴露隐藏剧情、私有规则原文、原始角色卡、密钥和存档。后端不得静态挂载 `data/`、`characters/` 或 `saves/`。
- 网页存储是 `backend/saves/<game_id>/game.json`，与 CLI SQLite 独立；保持单进程／单 worker、同局互斥和跨局隔离，不能直接扩成多 worker 服务。
- 随机结果先持久化、效果一次提交、正文最后保存；断线或重启恢复原请求，不重掷、不重复扣资源或发物品。损坏或不兼容须明确报错并保留现场。
- 模板与原始模组内容不因游玩被回写。运行配置变更需考虑已绑定指纹的旧局；GET 不写盘，不自动清空存档或强制迁移到最新剧情。
- 调整目录或资源路径时，同时验证 HTTP、CLI、内容加载和相关测试，避免破坏后端包与数据的相对路径。

## 开发与验证

- 新工作使用独立英文主题分支；脏工作区不得自动 stash/revert。结构迁移使用独立 worktree。
- 默认使用离线 demo、mock 和临时存档／数据库；不把玩家真实存档作为测试输入。付费模型评估须有明确任务授权，并遵守已授权范围；密钥仅放在 Git 忽略的本地配置。
- 后端代码验证：在 `backend/` 执行 `uv run --locked python -m unittest discover -s tests -t . -q`。
- 前端代码验证：在 `frontend/` 执行 `npm ci`、`npm run lint`、`npm run typecheck`、`npm run build`，以及受影响功能在开发指南中列出的接口检查。
- 纯文档变更检查差异、链接和表述一致性即可；未运行的检查及原因在交付时说明。
- 依赖声明变化同步锁文件；架构、接口、存储或启动流程变化同步相应文档和当前上下文。临时状态与实施记录不堆进本文件。
