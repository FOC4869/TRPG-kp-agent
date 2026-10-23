# 当前上下文

2026-10-22：在独立分支 feat/preset-investigator-data 按用户确认的格式新增十位预设调查员，位于 backend/data/characters/<id>/{character.yaml,background.md,assets/portrait.png}。无角色包层、无 manifest、无完整角色卡截图；结构不受现有 Character 实现约束。没有移动旧 Excel 或接入运行时/HTTP/前端。
角色数值、背景、原卡留白、装备和裁切头像已转录；作家伤害、记者历史/图书馆括号值等疑点保留在 source_issues，不自行裁定。魔术师钥匙特例是数据描述，尚无执行实现。字段约定见 backend/data/characters/README.md；交付记录见 docs/design/done/preset-investigators.md。
验证：十份 YAML 的唯一键/ID、属性技能范围、资源、攻击技能引用、嵌套装备、文件/锚点引用及十张 PNG 解码检查通过；头像合览人工检查通过；后端 191 项离线测试通过。无模型调用和依赖变更；本任务未修改前端，未重跑前端检查。原有首页及文档未提交改动保留，仅在 README/architecture/development/active-context 增补本次数据说明。
后续接入需单独实现角色目录加载、规则默认值与疑点裁定、角色实例快照及授权投影，不把静态数据完成等同于游戏功能完成。

2026-10-21：用户确认将项目初始化为 frontend（Vite React TypeScript）与 backend（FastAPI + 现有 LangGraph），在英文分支 chore/standardize-project-structure 实施。

源码从 7aa25aa 的 versions/ai-kp-v1 整体迁至 backend，根目录底层测试合并；底层与 Agent 均只有一份当前实现。前端由 Vite 官方命令生成。
HTTP 只提供 GET /api/health；React 页面用于检查连接。游戏接口、聊天页面、多人会话和数据库替换未实现。
依赖与启动以 README/development 为准。个人秘密、存档和虚拟环境不迁移。

下一步：在游戏 HTTP 接口实现前确认 KeeperService/SQLite 生命周期与请求隔离，更新接口契约；前端产品界面按实际需求另行设计。
目录迁移决策见 ADR-0001，路径和规则测试冲突见 history/structure-migration.md。

验证：191 项后端离线测试通过；CLI demo/重试、健康接口与 Vite 代理通过；前端 lint/typecheck/build 通过。未调用付费 API，未在本地运行 Windows 或远端 CI。完整初始化记录见 docs/design/done/project-bootstrap.md。
