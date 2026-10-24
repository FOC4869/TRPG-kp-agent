# 当前架构

项目采用 frontend/backend 单仓布局：React + FastAPI + LangGraph + DeepSeek。唯一源码入口为 frontend 与 backend。

## 网页运行链路

首页 → 模组库／详情 → 调查员 → 创建游戏 → `#/game?game=<game_id>` → 自由行动 → 游戏内结案弹窗。首页继续调查通过localStorage中的最近game_id和现有GET接口校验后进入原地址；保留游戏地址也可刷新或重启后恢复，不提供存档管理页。

目录为 React → Vite /api代理 → app/api/modules → Catalogue → 显式 module-catalogue.json发布清单／模组manifest／人物YAML。服务端构造公开DTO，不把原模板交给浏览器。封面位于对应模组assets，通过限定接口返回。清单的runtimeProfile将《岭下暗影》绑定到独立单人运行配置；preview是沿用的目录状态，不再单独用它判定可执行性。

游戏为 React → app/api/games → kp_agent/gameplay.GameRuntime → LangGraph（understand→execute_tools→narrate）。FastAPI仅校验、错误映射与生命周期，编排和状态提交在kp_agent，D100和损失骰调用trpg。模型返回结构化通用工具调用（move／observe／talk／take／inspect／interact／finish／use_item／drop／give／confirm_action），由执行节点校验模组配置、目标方法、前提与尝试次数。普通观察和在场NPC交谈无需逐句事件，关键效果仍来自服务端配置。模型不能直接写资源或存档。正文使用DeepSeek Responses真实流式输出，每轮正常最多两次调用。

内容由 `data/module-catalogue.json` 的 runtimeProfile 与 `data/runtime/index.json` 显式绑定，按本局 moduleId 延迟加载。v2 schema 校验场景、实体、NPC知识／可见性／跟随条件、挑战技能与道具、效果和结案条件；执行器和提示词不含专用模组／人物分支。支持已有工具能力的新模组只增加数据，接入步骤见[运行配置](runtime-profiles.md)和[ADR-0005](decisions/ADR-0005-module-driven-runtime.md)。

规划上下文包含当前合法工具与必要Keeper提示；叙述只包含已提交结果、当前公开描述、可见实体和NPC可说知识，不接收原始标志与未来剧情。场景的条件化公开描述覆盖最新进度。撤离与模组定义的代价确认用固定公开提示，不提前执行后续动作；其余正文真实流式生成。

《岭下暗影》新局运行 `data/runtime/darkness-solo-mvp-v4.json` 的十一场景调查扩充版。原v2、v3通过registry.retained固定指纹保留，已有游戏按原版本继续；原v1只升级到已冻结的v2。通用Ending的returnRoutes按条件选择返回地点，用于已准备的河岸出口，HTTP／SSE不变。原完整内容包继续只读，manifest的runtime_compatible:false仍准确；不宣称法术、复杂战斗或完整原模组可运行。原创天文台模组仅作为离线复用夹具，不进入产品目录。

实体actions编译到同一受控挑战执行器，布尔state效果仅引用声明字段。独立common-actions-v1物品能力按原始装备ID匹配并随局冻结；mechanics保存归属、实体状态与待确认动作。危险行动先持久确认，实际伤害使用trpg骰子、先保存出目再提交，effect消息/SSE不伪装D100。旧局只读补齐mechanics、不更换原剧情，见[ADR-0006](decisions/ADR-0006-common-actions.md)。

每局JSON位于backend/saves/<game_id>/game.json，保存初始模板快照、当前状态、完整消息、出目、请求和执行阶段。校验和、同目录临时文件、flush/fsync/原子替换、有效备份；损坏或不兼容显式报错，不自动重置/回滚。出目先保存、效果一次提交、正文最后保存；失败按检查点恢复。见[ADR-0004](decisions/ADR-0004-web-game-runtime.md)。

单进程／单worker，存档根目录进程锁防止多worker误用。同局请求接收锁与未决回合限制防止并发提交；任务独立于SSE订阅者，取消HTTP不取消行动。API只投影公开状态，素材按本局visited／揭示标志限定；不静态挂载data、characters、saves。详见[接口](interfaces.md)。明确登记的v1存档只向v2在内存升级，GET不写盘；下一次原子保存写v2并保留备份，旧出目、消息、请求与已提交效果不重做。未知版本不自动升级。

首页仅在浏览器记录一个最近打开的可恢复游戏编号，创建成功和有效游戏地址读取时更新；流式快照只清除已完成的同一局，不让旧局覆盖新局。主页重新进入、聚焦或跨标签编号变化时重新GET。明确404／完整结案清理编号，网络、损坏、版本错误保留并允许重试；终局但最终叙述待恢复仍可进入。没有新增后端API或模型调用，禁用本地存储时原URL恢复仍可用。

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
