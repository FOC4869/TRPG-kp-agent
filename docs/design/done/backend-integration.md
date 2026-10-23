# 后端逐页接入：M1–M4

2026-10-24：已完成可游玩单人MVP，分支feat/playable-mvp，保留此前目录／素材／文档工作区改动；未自动提交或推送。

| 阶段 | 实现 |
|---|---|
| M1 模组 | 从data/module-catalogue.json和模组manifest投影公开目录，引言与模组自身cover由API返回 |
| M2 调查员 | 十人YAML／背景／头像只读投影，选择页保留内部滚动 |
| M3 创建／恢复 | POST /api/games，人物快照、单局JSON、稳定地址和刷新恢复 |
| M4 行动／结案 | 独立LangGraph、真实DeepSeek、配置事件工具、SSE、检定卡、六场景与结案 |

FastAPI只适配HTTP。目录服务独立于模型；游戏运行器属于kp_agent/gameplay，数值调用trpg。CLI SQLite不复用为HTTP全局实例。网页不打包模板、私有模组或存档。

目录状态preview沿用旧字段；runtimeProfile显式绑定darkness-solo-mvp，只有绑定配置可创建游戏，原完整包仍不声称完全可执行。用户要求隐藏的年代／地点／人数／内容提示、预览来源、项目署名和设置入口没有重新放回页面。

[玩法](simplified-mvp.md)、[实现文件边界](playable-mvp-implementation.md)、[HTTP与SSE](../../interfaces.md)、[JSON与任务决定](../../decisions/ADR-0004-web-game-runtime.md)、[目录](../../catalogue-api.md)、[验证](../../evaluation/playable-mvp.md)。
