# 常见自由行动与自然 Keeper

2026-10-24，用户批准实现：自然回应、物品使用、取放交付、简单伤害、目标能力交互、确认和恢复。只扩展简化MVP，完整NPC战斗、法术与任意剧情改写不在本轮。

## 设计与状态

通用工具增加use_item/drop/give/confirm_action，take支持重新拾取；interact复用目标声明的actions。实体声明初始布尔状态、动作、允许技能与辅助能力、结果及公开状态描述，编译为原有受控交互，所有效果仍由后端配置决定。物品通过原始装备ID与独立common-actions-v1.json匹配；machete采用1D6简化伤害（明确改编、非原卡补全），徒手危险行为采用1D3。不实现NPC自由伤害；此类能力不足用简短Keeper裁定说明，不能编造角色自行收手。

新局保存mechanics/version/items/groundItems/npcItems/entityStates/activeItems/pendingAction；物品能力与版本快照不可被模型编辑。旧schema2存档在读取时通过模板指纹匹配显式增加mechanics（不写盘），首次行动保存；未知mechanics版本或模板变化明确报错，保留原局。旧剧情指纹和历史回合不变。新目标动作只发新内容v4，保留v3固定哈希；旧局也能使用通用物品、取放与伤害能力。

危险动作先保存pendingAction（原动作、场景、公开后果），不投骰或扣资源；确认或取消通过新回合执行。仅明确同意执行原动作，问题与假设不算确认。切换行动使旧确认失效，撤离确认与危险确认互斥；执行前重新校验物品与目标。出目先持久化，再提交效果；伤害记录单独damageRolls与effect消息，不伪装D100。普通动作无额外确认。

公开DTO增加pendingAction、nearbyItems；effect.resolved SSE和effect消息仅包含HP伤害明细。确认按钮提交自然语言且携带确认编号，服务端检查编号避免陈旧界面确认新动作。自然输入仍由Agent识别。UI保留内部滚动、旧D100动画与状态反馈。

## 文件与切片

1. schema.py/content.py/common_actions.py及独立规则JSON：能力快照、旧局只读升级、通用取放/交付/照明。验证十人物、缺参数、隔离、未知版本。
2. engine.py/runtime.py/agent.py：受控伤害、持久确认、自然叙述、effect SSE。验证确认/取消/陈旧确认/归零/断点恢复与不重复效果。
3. 运行配置v4和原创第二模组夹具：实体动作编译、技能/道具替代与持久实体状态。验证目标越权与无Python剧情分支。
4. 前端类型/API/卡片/按钮和脚本：伤害展示、拾取可见物品、确认恢复。npm ci/lint/typecheck/build及拆块SSE检查；1440×900、1280×720浏览器验证。

工程采用独立managed worktree feat/common-actions-work，复制当前相关脏基线，原工作区保持现场。集成前逐文件比较基线SHA256防止覆盖并行修改。规则调用trpg，不将编排放路由，不增加依赖，不修改原始模组/角色卡/真实存档。按Product→Eng→Design→Security→Code→QA顺序自审。完整后端离线门禁；本轮先离线验证，不新增付费生成调用。完成后同步接口/架构/开发/记忆及运行配置文档，再重启本地服务；不自动commit/push。

## 验收结果

- 全套274项后端离线测试通过；收尾提示词与前端失效确认处理调整后，26项相关测试再次通过。
- npm ci、lint、typecheck、build与四项离线适配检查通过；SSE覆盖逐字节中文、独立伤害、重复事件、非法结果及确认请求编号。
- current v4与retained v2/v3内容校验通过；原始v1/v2/v3、人物卡、完整模组内容不改。
- Playwright独立临时游戏、模拟Keeper在1440×900与1280×720检查确认、取消、刷新、真实后端投骰伤害、历史卡与减少动态效果；1280×720无整页溢出。另模拟其他标签取消旧动作，陈旧确认409后页面自动读取最新状态、未重复扣血。正常流程无控制台错误，陈旧确认的预期409除外。截图位于本地output/playwright/common-*.png。
- Product/Eng/Design/DX/Security/Code/QA按顺序自审：修复确认递归覆盖原计划的恢复风险、物品跨归属复制、旧撤离确认及陈旧UI确认；接口不暴露能力规则、私有计划、未来内容或密钥。
- 未调用真实模型：提示词的自然语言判断与语气已改，但不能以离线Agent替代DeepSeek实测结论。完整NPC战斗、任意物品组合和通用世界物理仍为后续范围。

已按基线SHA256校验集成30个任务文件到40da工作区feat/common-actions，保留之前相关未提交改动。集成后完整274项和前端npm ci/lint/typecheck/build及四项检查再次通过；健康/代理/玩家局只读GET为200，19个真实存档与备份字节不变。已重启原后端，临时QA服务已停止。
