# 调查员选择：已实现目录契约

2026-10-23。真实只读 HTTP 已接入，完整 URL、发布边界和错误见 [公开目录接口](catalogue-api.md)。游戏创建仍未实现。

`frontend/src/api/investigators.ts` 提供 `listInvestigators({moduleId,signal})` 与 `getInvestigator({moduleId,id,signal})`，使用 fetch、AbortSignal 和运行时响应校验。列表返回 module 的 id/title 与 items，客户端补充 source='api'；类型定义在 `frontend/src/types/investigators.ts`。

摘要包含 id、name、displayName（优先已有别名）、occupation、age（可空）、portrait.url。详情增加 overview、resources（HP/上限、SAN、MP/上限、幸运）、八属性、skills、background 段落、equipment、cash。未知量为 null，不等于零；没有 SAN 上限字段。

后端从登记人物 YAML 构造字段，overview 取背景“特质”；已知数值最高四项标为主要技能，不计算规则门槛或重新分配技能。Markdown 按二级标题解析，去掉结构锚点，原卡留空栏目返回 null。物品展平并保留容器名称、数量、单位、拥有资产标记与未知参数，特殊效果仅展示原卡说明和未实现提示。不静默修正争议值，不发送 source/source_issues、原卡或模板全文。

无 module 或模组未开放时提示返回，不默认选模组。列表与详情分开请求；卸载／切换取消旧请求，只在详情 ID 与当前选择一致时启用确认。支持 loading、空、错误／重试，AbortError 不展示为错误。列表404映射 module-unavailable；详情404映射 investigator-unavailable；服务故障保留重试，不降级假人物。

确认弹窗核对案件与人物，进入保留 module/investigator 参数的游戏预览。游戏页读取真实人物展示资料，但开场、动作和结案仍为演示，不创建 game_id、保存状态、编辑背景或执行物品特例。服务端角色快照与模板版本绑定留待 M3。

2026-10-24：确认调查员已改为调用POST /api/games创建真实游戏；旧的module/investigator游戏预览URL不再用作恢复入口。创建失败保留相同请求ID，成功导航到#/game?game=<id>。模板只读，实例独立保存；游戏契约见[interfaces](interfaces.md)。
