# 当前上下文

2026-10-23：将 feat/preset-investigator-data 合并回 design/frontend-ui；保留目标分支现有模组库/详情页及《岭下暗影》内容包，新增十位预设调查员。角色目录仍未接入页面和游戏运行链路。

2026-10-22：在独立分支 feat/preset-investigator-data 按用户确认的格式新增十位预设调查员，位于 backend/data/characters/<id>/{character.yaml,background.md,assets/portrait.png}。无角色包层、无 manifest、无完整角色卡截图；结构不受现有 Character 实现约束。没有移动旧 Excel 或接入运行时/HTTP/前端。
角色数值、背景、原卡留白、装备和裁切头像已转录；作家伤害、记者历史/图书馆括号值等疑点保留在 source_issues，不自行裁定。魔术师钥匙特例是数据描述，尚无执行实现。字段约定见 backend/data/characters/README.md；交付记录见 docs/design/done/preset-investigators.md。
验证：十份 YAML 的唯一键/ID、属性技能范围、资源、攻击技能引用、嵌套装备、文件/锚点引用及十张 PNG 解码检查通过；头像合览人工检查通过；后端 191 项离线测试通过。无模型调用和依赖变更；本任务未修改前端，未重跑前端检查。原有首页及文档未提交改动保留，仅在 README/architecture/development/active-context 增补本次数据说明。
后续接入需单独实现角色目录加载、规则默认值与疑点裁定、角色实例快照及授权投影，不把静态数据完成等同于游戏功能完成。

2026-10-23：将 feat/darkness-module-package 合并回 design/frontend-ui；保留现有首页/模组库，新增服务端模组内容包。两者尚未接成游戏运行链路。

2026-10-22：在独立工作树 darkness-module、分支 feat/darkness-module-package 新增《岭下暗影》内容包。基于创建时 HEAD 20494e4，未带入原工作区 design/frontend-ui 的未提交首页改动。

交付：backend/data/modules/darkness-beneath-the-hill/，完整正文38锚点、10个YAML、45个事件提取、7张原图与2份正文展示材料索引；assets/统一存储，无固定媒体分类子目录。素材原始字节保留，默认keeper_only。

范围：声明式内容草案，不改变现有campaign.json、KeeperService、CLI、HTTP、前端或SQLite；未实现运行时加载/检索/授权。原文规则争议、地图逐边核准与外部规则依赖见包内issues.yaml。

验证：完整正文往返、YAML重复键/出处/实体引用、素材哈希、默认权限检查通过；后端191项离线单测通过。未改前端，未运行前端检查；未调用真实模型。设计与验证见 docs/design/done/darkness-module-package.md。

下一步：先核准地图连接、规则版本、蛇人HP与其他issues，再单独设计内容schema/loader到执行器的适配；不要将此包直接交给现有--campaign加载器。

以下为前端与工程交付记录：

2026-10-22 后续：用户要求先提交首页再实现模组库；首页已提交 ace06d5。
当前新增分页模组库/详情（#/modules），桌面每页 3 张卡片、左右翻页、首尾禁用、末页不补空卡。首页开始调查已跳转新页面；选择调查员仅弹出尚未开放提示。
主模组确定为《岭下暗影》，只使用用户提供的玩家引言，封面表现地窖/提灯/未知通道，不传守秘人信息。api/modules.ts 暂时读取本地 typed fixture（1 个主模组 + 6 条待收录记录），不请求不存在的后端目录接口。
新封面为内置 imagegen 原创生成；底层与后端未改。下一步为调查员选择界面；接游戏 API 前仍需确认存储与服务生命周期。
验证：npm ci/lint/typecheck/build、分页适配 smoke、桌面/宽屏/短屏/窄屏浏览器检查、选择/翻页/焦点/返回/刷新均通过。交付记录见 docs/design/done/module-library.md；完整素材提示词归档 docs/design/image-assets.md。

以下为首页交付记录：

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
