# 当前上下文

2026-10-22：在独立工作树 darkness-module、分支 feat/darkness-module-package 新增《岭下暗影》内容包。基于创建时 HEAD 20494e4，未带入原工作区 design/frontend-ui 的未提交首页改动。

交付：backend/data/modules/darkness-beneath-the-hill/，完整正文38锚点、10个YAML、45个事件提取、7张原图与2份正文展示材料索引；assets/统一存储，无固定媒体分类子目录。素材原始字节保留，默认keeper_only。

范围：声明式内容草案，不改变现有campaign.json、KeeperService、CLI、HTTP、前端或SQLite；未实现运行时加载/检索/授权。原文规则争议、地图逐边核准与外部规则依赖见包内issues.yaml。

验证：完整正文往返、YAML重复键/出处/实体引用、素材哈希、默认权限检查通过；后端191项离线单测通过。未改前端，未运行前端检查；未调用真实模型。设计与验证见 docs/design/done/darkness-module-package.md。

下一步：先核准地图连接、规则版本、蛇人HP与其他issues，再单独设计内容schema/loader到执行器的适配；不要将此包直接交给现有--campaign加载器。

以下为创建分支时的历史上下文：


2026-10-21：用户确认将项目初始化为 frontend（Vite React TypeScript）与 backend（FastAPI + 现有 LangGraph），在英文分支 chore/standardize-project-structure 实施。

源码从 7aa25aa 的 versions/ai-kp-v1 整体迁至 backend，根目录底层测试合并；底层与 Agent 均只有一份当前实现。前端由 Vite 官方命令生成。
HTTP 只提供 GET /api/health；React 页面用于检查连接。游戏接口、聊天页面、多人会话和数据库替换未实现。
依赖与启动以 README/development 为准。个人秘密、存档和虚拟环境不迁移。

下一步：在游戏 HTTP 接口实现前确认 KeeperService/SQLite 生命周期与请求隔离，更新接口契约；前端产品界面按实际需求另行设计。
目录迁移决策见 ADR-0001，路径和规则测试冲突见 history/structure-migration.md。

验证：191 项后端离线测试通过；CLI demo/重试、健康接口与 Vite 代理通过；前端 lint/typecheck/build 通过。未调用付费 API，未在本地运行 Windows 或远端 CI。完整初始化记录见 docs/design/done/project-bootstrap.md。
