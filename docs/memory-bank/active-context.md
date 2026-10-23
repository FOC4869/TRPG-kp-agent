# 当前上下文

2026-10-23：按用户要求删除 .github/workflows/ci.yml，后端测试和前端 lint/typecheck/build 改为开发者提交前手动执行。历史初始化报告中的 CI 描述仅反映当时状态。

2026-10-23：design/frontend-ui 已快进合并到 taosdev。按当前 frontend/backend/skills 目录调整根 .gitignore、.gitattributes、.editorconfig：运行输出按目录忽略，JSONL/ZIP 样本和素材不再全局排除，保留依赖锁和评估证据。

2026-10-23：经用户要求，将 coc-module-builder 提交并合并到 design/frontend-ui；保留角色卡导入 skill 及前端已有功能。合并验证继续使用该 skill 的 34 项离线测试，真实素材试制另行进行。

2026-10-23：经用户要求，将角色卡导入 skill 提交并合并至 design/frontend-ui，保留该分支已有调查员选择页。技能仍为独立工具，不接游戏运行时。

2026-10-23：在 feat/coc-character-import-skill 新增自包含技能 skills/coc-character-card-import/，固定生成 character.yaml、background.md、可选裁切头像，无 manifest，不依赖本项目角色类、数据或对话。项目目录是维护源，已按普通文件复制到个人 Codex skills 目录，未自动提交/推送。
验证：quick_validate 对源码/安装副本通过；29 个隔离脚本场景通过；仅给技能和三张图片的独立试用完成 3 位角色，局部复核修正字符误读，最终 0 错误，原文疑点保留为警告；已有十人只读校验 0 错误。npx skills 本地发现及临时项目 --copy 安装通过，最终文件与维护源逐字节相同；后端191项通过。未修改前端/运行时/已有角色，未调用外部模型API。交付记录见 docs/design/done/coc-character-import-skill.md。
后续：GitHub 默认分支发布后，外部用户才能直接用 npx skills add FOC4869/TRPG-kp-agent 获取此技能；尚未验证远端安装。独立原图复核还发现既有 david 卡将“一双手铐”记成 quantity=2、unit=双，属于待单独修订的数据错误，本轮按约定未改旧角色。

2026-10-23：在独立 worktree 的 feat/coc-module-builder-skill 实现 skills/coc-module-builder，可通过 Skills CLI 本地安装，完整携带内容格式、原创模板、视觉生产规范、制作计划与只读校验器。用户要求无需当前聊天上下文也能产出相同结构；默认前三阶段为整理、规划、首批样本，选定风格后续做。未迁移现有模组、未生成真实图片、未接运行时/HTTP/前端，未推送或发布。验证结果见 docs/design/done/coc-module-builder.md。

2026-10-23 后续：按用户确认的概念图实现调查员选择，仍在 design/frontend-ui；用户明确要求先用假数据和假资源，后续从 API 获得正式数据。
页面为 #/investigators?module=<id>，桌面 2×5 照片卡片，右侧概览/属性技能/背景/物品四标签。首次无选择，确认禁用；选中后可打开案件/人物确认摘要，不创建游戏或存档。
后续按用户反馈稳定右侧档案高度：四标签内容内部滚动，头像/标签/确认按钮位置固定，切换标签不再拉高整页。已检查桌面与窄屏、键盘滚动。
types/investigators.ts 定义公开展示类型，api/investigators.ts 提供 listInvestigators/getInvestigator（moduleId + AbortSignal）；当前读取独立 mock，未读取/复制 backend/data/characters 的 YAML/头像/背景。假头像图集由内置 imagegen 生成，素材提示词归档 docs/design/image-assets.md。
接入契约见 docs/investigator-api.md。下一步为游戏界面；正式 HTTP、授权摘要与模板实例/存档生命周期另行实现。
验证：npm ci/lint/typecheck/build、适配层 smoke、桌面/宽屏/短屏/窄屏浏览器检查、四标签键盘导航、选择确认与无效上下文均通过；无后端改动，未重复后端测试。交付记录见 docs/design/done/investigator-selection.md。

以下为服务端资产合并历史：

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
