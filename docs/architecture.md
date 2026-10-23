# 当前架构

项目采用 frontend/backend 单仓布局：React + FastAPI + LangGraph + DeepSeek。唯一源码入口为 frontend 与 backend。

## 网页运行链路

首页 → 模组库／详情 → 调查员 → 创建游戏 → `#/game?game=<game_id>` → 自由行动 → 游戏内结案弹窗。继续调查入口仍灰显；保留游戏地址可刷新或重启后恢复，不提供存档管理页。

目录为 React → Vite /api代理 → app/api/modules → Catalogue → 显式 module-catalogue.json发布清单／模组manifest／人物YAML。服务端构造公开DTO，不把原模板交给浏览器。封面位于对应模组assets，通过限定接口返回。清单的runtimeProfile将《岭下暗影》绑定到独立单人运行配置；preview是沿用的目录状态，不再单独用它判定可执行性。

游戏为 React → app/api/games → kp_agent/gameplay.GameRuntime → LangGraph（understand→execute_tools→narrate）。FastAPI仅校验、错误映射与生命周期，编排和状态提交在kp_agent，D100和损失骰调用trpg。模型返回结构化事件选择，由执行节点校验配置、目标方法、前提与尝试次数后分派工具。模型不能直接写资源或存档。正文使用DeepSeek Responses真实流式输出，每轮正常最多两次调用。

叙述上下文按当前已提交状态重建通路、牢笼和乔什阶段，近期对话不覆盖最新事实。撤离和固定HP代价的确认使用运行器生成的固定提示，先告知再等待下一行动；此类回合只需要行动理解调用。其余正文由模型主持，数值与结案仍以执行器为准。

`backend/data/runtime/darkness-solo-mvp-v1.json`是唯一网页玩法配置，含六场景、两条乔什时间线、事件条件/效果/检定/重复规则与授权素材引用。原完整内容包继续只读，manifest的runtime_compatible:false仍准确：此次只声明独立简化配置可执行，不宣称法术、复杂战斗或原完整模组可运行。

每局JSON位于backend/saves/<game_id>/game.json，保存初始模板快照、当前状态、完整消息、出目、请求和执行阶段。校验和、同目录临时文件、flush/fsync/原子替换、有效备份；损坏或不兼容显式报错，不自动重置/回滚。出目先保存、效果一次提交、正文最后保存；失败按检查点恢复。见[ADR-0004](decisions/ADR-0004-web-game-runtime.md)。

单进程／单worker，存档根目录进程锁防止多worker误用。同局请求接收锁与未决回合限制防止并发提交；任务独立于SSE订阅者，取消HTTP不取消行动。API只投影公开状态，素材按本局visited／揭示标志限定；不静态挂载data、characters、saves。详见[接口](interfaces.md)。

## CLI 与目录边界

CLI → 原KeeperService／LangGraph → RAG、trpg、SQLite，保留独立连接生命周期与active_game语义，不与网页共享。旧故事存档不迁移为网页JSON。

- frontend/src：UI、HTTP与SSE适配、类型和样式；无模型密钥／原始模组剧情。
- frontend/public/images：首页及暂保留的旧开场图；正式游戏不引用预览素材。
- backend/app：HTTP；导入应用和健康检查不加载模型、不创建玩家存档。
- backend/kp_agent/gameplay：网页内容加载、JSON存储、规则工具、LangGraph、后台任务及公开投影。
- backend/kp_agent其他文件：既有CLI Agent、RAG与SQLite适配。
- backend/trpg：唯一数值规则与骰子实现。
- backend/data/modules与data/characters：原始只读模组／十位人物数据；frontend不打包它们。
- backend/data/runtime：独立网页简化改编；backend/saves/output/logs：Git忽略的本地状态和评估证据。
- skills：可独立安装的制作／导入工具，不属于HTTP运行时。

## 工程约束

Python3.12／uv，Node24／npm；锁文件固定依赖。单进程本地监听回环地址，Vite转发/api至8000；不开放通配CORS。部署需要同源反向代理并重新设计鉴权、多进程事务存储，当前游戏URL仅是本地恢复凭证。

完整内容包、裁定和素材来源分别见[ADR-0002](decisions/ADR-0002-module-content-package.md)、[模组README](../backend/data/modules/darkness-beneath-the-hill/README.md)和其rulings.yaml。目录发布决定见[ADR-0003](decisions/ADR-0003-public-catalogue.md)。目录迁移见[ADR-0001](decisions/ADR-0001-project-layout.md)。
