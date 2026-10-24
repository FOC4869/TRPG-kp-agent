# ADR-0003：只读公开模组与调查员目录

2026-10-23，接受。

玩家选择页需要真实资料，但模组包默认 keeper_only，完整文件不能通过静态目录暴露。使用 backend/data/module-catalogue.json 显式登记模组映射、公开引言、封面及允许的调查员 ID；标题读取 manifest，调查员读取 YAML/Markdown 后投影为公开 DTO。封面归属模组 assets，manifest.presentation.cover 与发布清单 coverAsset 显式关联素材索引中的 module_cover；头像按已登记人物提供独立路由。2026-10-23按用户要求修订，删除此前额外 data/public 目录。所有文件路径解析后限定在各自根目录内。

不采用自动扫描并公开全部包或整个 assets 静态挂载，避免草案/隐藏内容泄露；不把 YAML 复制至 frontend。代价是发布新内容需登记允许清单。GET 无数据库、模型和模板写入；游戏创建/规则仍单独适配 kp_agent/trpg。preview 表示页面预览，不代表模组执行器已实现。
