# 预设调查员

本目录保存用户提供的十位预设调查员，每个角色独立成目录，无角色包层和 manifest。
这里只交付数据，尚未实现目录加载器、角色选择接口或网页。原有 CLI / Excel 流程不引用这些数据。

```text
characters/
├── <角色ID>/
│   ├── character.yaml
│   ├── background.md
│   └── assets/
│       └── portrait.png
└── README.md
```

| ID | 姓名 | 职业 |
|---|---|---|
| stanley | 史丹利·艾斯 | 拳击手 |
| jessica | 杰西卡·布鲁克斯 | 作家 |
| melissa | 梅丽莎·德弗丽丝 | 科学家 |
| jacob | 雅各布·吉普森 | 门卫 |
| john_lucas | 约翰·卢卡斯医生 | 内科医生 |
| david | 大卫“不可思议的克雷格”威尔考克斯 | 舞台魔术师 |
| chris | 克丽斯·帕克 | 地质学教授 |
| stephen | 史蒂芬·谢泼洛夫斯基神父 | 天主教神父 |
| geraldine | 杰拉尔丁“格里”桑希尔 | 记者 |
| maximilian | 麦克斯米兰·赫斯特 | 心理学家 |

## 格式 1.0

- `schema_version` 是文件格式版本；`version` 是角色模板内容版本；`id` 是稳定引用，不依赖显示名称。
- `name`、`age`、`occupation` 和可选 `aliases` 是角色身份，不从职业推导额外能力。
- `background` 指向背景正文，`assets` 是以素材 ID 为键的附件索引。
- 所有文件引用相对 character.yaml 所在目录；未来加载器应拒绝越出该目录的路径和符号链接。不按文件夹名称推断附件类型或权限。
- `attributes` 保存八属性；`initial_resources` 保存原卡开局 HP、SAN、MP、幸运；`authored_derived` 保存原卡 HP/MP 上限、移动、DB、体格。HP/MP 按预设卡完整开局资源解释，上限记录为原卡值；原卡没有 SAN 上限，文件不补填。
- `skills` 保存最终基础成功率（非投入点数）；缺失技能表示原卡未列出，不表示零，也不授权加载器自行按职业推断。是否采用规则默认值留给后续明确的规则配置。
- 仅统一展示名称：躲闪→闪避、艺术/手艺→艺术与手艺、领航→导航；专长仍保留在名称中。科学（Forensics）保留原卡英文，未自行翻译或合并。
- 困难/极难阈值不复制存储，未来按明确的规则配置计算。原卡冲突的括号值记录在 `source_issues`，不静默改基础值。
- `attacks[].skill` 必须引用 skills 中的键；`damage.base` 与 `add_damage_bonus` 表示基础伤害与是否加角色 DB。武器攻击不再重复存储技能数值。原卡未加 DB 的攻击保留该表达，不泛化为所有武器都加 DB。
- 伤害存在冲突时使用 `damage.status: needs_review`、保留 `source_expression`，base 和 add_damage_bonus 为 null；执行器必须先解决疑点，不能直接执行原始字符串。
- `starting_equipment` 可含嵌套 contents；quantity 为 null 表示原卡未给出具体数量。quantity=1 的工具包或成套装备代表一整套，不推测内部数量。
- `placement: owned_asset` 表示汽车等拥有资产；其他装备为初始装备，实际携带和位置由开局确认及存档管理。医疗箱、科学箱等内容不详时不自行展开。
- 弹药、长度、战斗参数等未知量明确为 null 或标记 details_unspecified / contents_unspecified，不等于无限、不需消耗或可直接使用。
- `special_effects` 仅描述原卡物品特例；requires_runtime_implementation 表示还没有执行能力。大卫钥匙的 80% 成功率不覆盖锁匠技能。
- `starting_money` 与信用评级独立。每位角色原卡均列 10 美元现金。
- `customization` 列出原卡留空或未提供内容的可填写栏目，anchor 指向背景中的稳定锚点。固定人物叙述以 background.md 为依据，YAML 不重复维护文本。
- `source` 只记录用户提供截图的序号和来源说明；不存完整角色卡截图。portrait.png 从原图无生成地裁切，保留原相框，无其他改画。
- `source_issues` 保存疑点，status=needs_review 表示尚未裁定。原卡中的轻微遣词、称呼差异保留在背景中；神父卡的译注也保留。

## 使用与边界

未来可扫描 `*/character.yaml` 枚举全部角色，用 id 建索引；模组按 id 引用，不复制模板。
模板只读，玩家填写和本局 HP/SAN/MP、装备消耗等变化进入存档；实例绑定模板 ID、版本并保留开局快照。
背景中的宝贵之物不自动追加到随身装备，也不根据物品名称授予幸运或其他奖励。
原卡列出攻击不等于装备表明确授予该武器；门卫的扳手、医生的手术刀已标记这一差别。

本目录所有文件是后端资产，不得复制进前端构建或整体作为静态目录公开。
角色选择页未来通过后端获得授权摘要及头像，具体权限另行设计。
旧 `backend/characters/` Excel 保留原路径；本次不做迁移或兼容适配。

## 已知原卡疑点

- 杰西卡 DB 为 +1D4，徒手伤害却为 1D3+1D6，结构化伤害暂不可执行。
- 格里历史写为 9%（15/6）、图书馆使用 50%（12/10），保留基础值 9 和 50，标记冲突。
- 部分道具缺少武器参数、数量或内容，不能据名称补全；详见各角色配置。

以上数据尚未接入游戏引擎，不能把完成转录视为对应战斗、装备和物品特例已实现。
