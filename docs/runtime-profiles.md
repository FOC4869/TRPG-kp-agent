# 模组运行配置接入

当前网页采用“结构化内容＋Agent 通用工具”。原文、NPC 和素材仍放在 `backend/data/modules/<directory>/`；可执行范围另写为 `backend/data/runtime/<profile>-vN.json`。原文内容包不因此被声明为完整可执行，制作 skill 输出也仍需整理为运行配置。

## 接入步骤

1. 按现有内容格式提供 `manifest.yaml`、素材索引、合法背景／立绘文件和公开封面。角色从现有 `data/characters` 选择。
2. 编写 schemaVersion=2 的运行配置。完整原创例子见 [天文台测试配置](../backend/tests/fixtures/runtime/observatory-v1.json)，正式配置见 [岭下暗影目标交互版 v4](../backend/data/runtime/darkness-solo-mvp-v4.json)。测试例子的图像 ID 由临时测试目录提供，不注册到产品目录。
3. 在 `data/module-catalogue.json` 登记公开模组、调查员和 `runtimeProfile`；在 `data/runtime/index.json` 登记同名 profile、moduleId 和 current 文件。三者必须相符，不自动扫描目录或猜测名字。
4. 启动前运行下方只读检查，再用离线 Agent 验证路线、检定失败、重复、素材及知识边界，最后经明确授权进行真实模型试玩。内容加载按模块延迟执行，修改内容后重启服务。

```sh
cd backend
uv run --locked python -m kp_agent.gameplay.validate_content
uv run --locked python -m unittest tests.test_module_runtime tests.test_darkness_investigation tests.test_web_game tests.test_web_game_http -q
```

支持已有机制的新模组只需数据，无需增加 Python 分支。新机制（完整战斗、法术等）需要先扩展并测试通用工具，不能仅在剧情文字里描述就视为实现。

## 配置字段

| 字段 | 用途 |
|---|---|
| id / moduleId / version / schemaVersion | 注册绑定与存档指纹 |
| initial | 开局 scene、全部 flags、每个 NPC 的 stage/location/topics |
| opening | 公开开场消息，keeper 或 npc |
| scenes | 名称、地区、背景、公开描述、仅供规划的 keeper 提示、按条件拼接的公开 clauses |
| npcs | 名称、角色、立绘、公开外貌、出现条件 visibleWhen、跟随条件 followsWhen、可说知识 knowledge |
| entities | 场景内可见目标及公开描述，scenes/requires 控制可见性；可选 initialState、条件 clauses 和 actions |
| affordances | 关键交互：tool/target/option、场景、前提、次数、效果和可选 challenge |
| endings | 安全结束场景、默认返回地点、可选 returnRoutes 条件返回地点（首个匹配）、完成条件、撤离确认、三类结案事实及 clauses |
| itemAliases | 人物模板物品名称到模组道具 ID 的显式别名；未匹配的物品保留独立 ID |
| assetGrants | 额外已揭示素材授权；已到访场景的背景和当前可见 NPC 立绘自动可用 |
| legacyActions | 仅用于明确登记的旧存档兼容，新模组可省略 |

NPC 初始位置必须存在，所有 NPC（包括后续才出现的角色）均需声明。NPC 不自动进行检定；followsWhen 为真时随玩家移动。没有 NPC 的模组可使用空字典。

## 通用工具与自由行动

Agent 每轮只提交一个结构化计划：kind 为 tool/question/clarify/unsupported；tool 包含 name、target、option、skill、item、approach。模型没有写存档或任意修改资源的工具。

| 工具 | 边界 |
|---|---|
| observe | 观察当前场景、可见实体／NPC；只返回公开描述，不发放新线索或跳过挑战 |
| talk | 与在场 NPC 普通交谈无需枚举事件；关键话题用 option 绑定配置效果 |
| move | 目标必须为当前允许的场景连接，普通回头不结案 |
| take / inspect / interact | 关键取物、调查与挑战必须匹配配置中的目标／选项和前提 |
| use_item | 使用持有物品照明、以工具执行合法目标动作，或先确认再结算简化自我伤害 |
| drop / give | 放下整个物品条目或交给在场 NPC 保管，不自动换取剧情收益 |
| confirm_action | 只执行或取消当前持久化的危险行动，确认前重新校验方法与物品 |
| finish | target=investigation，request／confirm／cancel；安全场景可直接结束，其余先明确确认 |

例如“我用工具调整锁簧”可映射到同一个舱门挑战的机械维修方法；“我用钥匙”可选择配置的 aid。无需为每句话创建事件。Agent 可将临场策略映射到允许的技能与道具；不在配置能力范围内的法术、任意道具组合等明确解释或澄清，不悄悄换成另一种行为。

`challenge.skills` 为允许的技能／属性；`aids` 为已有物品中可免检定的辅助 ID。技能与物品二选一；失败损失为 hp/san 与受限骰子表达式，成功／失败分别执行配置效果，然后执行共有 effects。当前只支持基础技能表、八项属性和 SAN。

repeat=once 限制整个交互，always 允许重做，method 按“交互＋技能／道具”记录尝试。换措辞不增加次数，已用方法不进入规划选项；道具辅助仍可在另一个技能失败后使用。固定 check 效果按原顺序运行，D100 和损失骰均调用 trpg。每个保存的随机结果都有稳定 checkId。

## 条件与效果

实体可声明 actions：id/label/description、skills、aids（light/rope/pry/cut/key 能力标签）、requires、effects、success/failure、failureLoss、dangerous、repeat。运行器编译为 interact/实体ID/动作ID；state 效果只可修改该配置声明的 initialState 布尔字段，clauses 按状态更新公开描述。`supply_case` 和原创天文台的 `cabinet` 验证了同一机制，不含模组专用 Python 分支。危险动作先确认；技能/工具挑战复用现有出目、免检定辅助和重试约束。

通用物品能力来自独立 `common-actions-v1.json`，按原始角色装备 ID 匹配、随游戏冻结。大砍刀1D6和徒手1D3是MVP改编，原卡缺失数据不回写。照明只改变已知物品状态，不免费揭示隐藏线索。取放与NPC保管保持唯一归属；配置取物不能复制已交付的物品。

条件支持 all/any/not、entity:ID:field、scene、ending、flag:ID、item:ID、clue:ID、visited:ID、npc:ID:stage/location；check:ID 只用于同一行动效果的本轮检定结果。空条件为真，空 any 为假。无表达式执行、Python 回调或自由数值 patch。

效果只支持 flag、move、npc、clue、item、check、loss、state。模型不能提供效果列表；实际效果从服务器配置读取。clue 只记录信息，不等于带走实物；item 才入背包。HP/SAN 归零立即失败并停止后续效果。

## 公开与私有边界

规划模型仅得到当前可用工具、可见目标和必要 Keeper 提示；不加载整份隐藏原文。叙述模型只得到已提交结果、当前公开场景、可见实体、NPC 允许表达的知识、已发现事实及近期对话，不接收原始 flags、挑战效果或未来场景。NPC知识需由作者按条件限制，运行器不会自行猜测其应知范围。

HTTP／SSE 仍只返回公开快照。素材接口根据本局到访、当前 NPC 和 assetGrants 授权，不返回模组目录路径或任意素材。网页标题和地区均来自本局配置／清单。

## 存档版本与恢复

每局绑定配置原始 JSON 指纹与内容清单指纹。未知版本／结构损坏明确报错，保留文件；改剧情后不能靠改版本号强行加载旧局。新局使用 registry.current；已登记在 retained 的固定指纹按原配置继续。另提供显式登记的 v1→v2 升级，没有通用任意版本迁移承诺。

原《岭下暗影》v1 文件保留不变；index.compatible 指定来源及冻结的目标指纹。读取时在内存转换初始缺省项、旧计划和尝试；GET 不写盘。下次行动通过原有原子提交保存 v2 并保留有效备份。出目、checkId、消息、请求 ID、已提交资源与剧情效果均保留；旧待提交计划使用已保存随机数，已提交回合只补叙述。未知旧指纹拒绝自动升级。


《岭下暗影》新局为v4（4.0.0），增加地窖工具箱的声明式开锁／破坏／取物交互。v2、v3原始JSON及指纹均保留在index.retained；原局和重复创建请求继续原故事，v1仍只升级到v2。发布新内容时增加独立文件，不能修改旧版本。新版损坏不阻塞旧局，旧版损坏明确报错，校验命令检查current、retained及迁移目标。

mechanics 是独立 version=1 的持久状态，包含冻结能力、地面／NPC物品归属、实体状态、启用物品和待确认动作。旧局通过匹配 templateHash 的原模板在内存补充，GET不写盘；首次行动才保存。旧剧情不升级到v4，但可使用通用取放、照明、交付和简化伤害。未知版本或模板变化明确报错保留存档。

扩充版11个场景、61个关键交互／移动定义、23类可发现线索。支线不是必做清单：旧信与撬棍可准备河岸出口，仔细看清陷坑可绕行，完整演奏以明示1SAN换取声音掩护，家族资料与俘虏遗言／可疑饮水可支持安抚；技能失败均有替代做法。原文依据、改编边界、选择与验收见[调查扩充](design/done/darkness-investigation.md)。没有新增规则Python特判或前端剧情副本。
