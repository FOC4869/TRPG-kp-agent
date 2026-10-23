# 人物存储结构

更新日期：2026-10-23。覆盖玩家预设调查员和模组 NPC／生物；两者格式、用途和生命周期不同。字段细节以实际文件和[调查员说明](../backend/data/characters/README.md)为准。

## 1. 数据分别放在哪里

| 类型 | 位置 | 当前用途 |
|---|---|---|
| 预设调查员模板 | `backend/data/characters/<id>/` | 十位原卡转录资料，已接网页只读目录，未创建运行实例 |
| NPC／生物 | `backend/data/modules/<module-directory>/characters.yaml` | 随模组存放定义、实例和群组，引用同包立绘 |

`backend/characters/` 仍有旧 CLI 使用的 Excel 卡，不能与 `backend/data/characters/` 混为一谈。现有 CLI 没有自动改用新 YAML 模板。

## 2. 预设调查员目录

```text
backend/data/characters/
├── README.md
├── chris/
│   ├── character.yaml       # 身份、数值、装备、来源
│   ├── background.md        # 背景正文与稳定锚点
│   └── assets/
│       └── portrait.png     # 原卡裁切头像
├── jessica/
│   └── ...
└── <其他调查员ID>/
    └── ...
```

每位人物独立成目录，没有角色包层或全局 `manifest.yaml`。十位人物均有上述文件。目录服务仅读取 module-catalogue.json 显式登记的 investigatorIds；新增文件不会自动对玩家公开。

| ID | 姓名 | 职业 |
|---|---|---|
| `stanley` | 史丹利·艾斯 | 拳击手 |
| `jessica` | 杰西卡·布鲁克斯 | 作家 |
| `melissa` | 梅丽莎·德弗丽丝 | 科学家 |
| `jacob` | 雅各布·吉普森 | 门卫 |
| `john_lucas` | 约翰·卢卡斯医生 | 内科医生 |
| `david` | 大卫“不可思议的克雷格”威尔考克斯 | 舞台魔术师 |
| `chris` | 克丽斯·帕克 | 地质学教授 |
| `stephen` | 史蒂芬·谢泼洛夫斯基神父 | 天主教神父 |
| `geraldine` | 杰拉尔丁“格里”桑希尔 | 记者 |
| `maximilian` | 麦克斯米兰·赫斯特 | 心理学家 |

姓名用于展示，ID 用于引用。模组通过发布清单 investigatorIds 关联调查员 ID，不复制目录。

## 3. character.yaml 保存什么

| 字段 | 内容与约束 |
|---|---|
| `schema_version` / `version` | 文件格式和人物模板版本，当前分别为 `1.0` / `1.0.0` |
| `id`、`name`、`age`、`occupation`、可选 `aliases` | 稳定身份与展示资料 |
| `background` | 背景 Markdown 路径，不重复存整段经历 |
| `assets` | 以素材 ID 为键的附件索引，如 `portrait.file` |
| `attributes` | STR、CON、SIZ、DEX、INT、APP、POW、EDU 八属性 |
| `initial_resources` | 开局 HP、SAN、MP、幸运 |
| `authored_derived` | 原卡 HP／MP 上限、移动、DB、体格 |
| `skills` | 技能名称到最终基础成功率的映射，不是投入点数 |
| `attacks` | 攻击 ID、名称、技能引用、基础伤害及是否加 DB |
| `starting_equipment` | 可嵌套 `contents`，保留数量、单位、位置和未知参数 |
| `starting_money` | 独立现金；原卡均为 10 USD，不等同信用评级 |
| `customization` | 可填写栏目和背景锚点，不代表网页已支持编辑 |
| `source` / `source_issues` | 来源说明和疑点，不原样公开给玩家 |

真实模板的身份／资源节选如下，完整资料以原文件为准：

```yaml
schema_version: '1.0'
version: 1.0.0
id: chris
name: 克丽斯·帕克
age: 39
occupation: 地质学教授
background: background.md
assets:
  portrait:
    file: assets/portrait.png
    media_type: image/png
initial_resources:
  hp: 10
  san: 55
  mp: 11
  luck: 60
```

文件引用相对 `character.yaml` 所在目录。未来加载器需校验路径与符号链接，拒绝越出人物目录。头像为原卡裁切，不是 NPC 透明立绘；目录不保存完整角色卡截图。

## 4. 背景正文与留白

`background.md` 保存人物描述、特质、信念、重要之人、地点、宝贵之物、经历等正文，并设置稳定 HTML 锚点。`customization[].anchor` 指向可填写部分，原卡留白继续保留，不由导入流程补写。

背景“宝贵之物”不自动加入背包，人物经历不自动授予技能、装备或奖励。前端示例背景不是后端原卡正文的同步副本。

## 5. 模板资料与可执行规则的区别

- 缺失技能表示原卡未列出，不代表零；补规则默认值需要明确配置。
- SAN 不补上限。困难／极难阈值不重复存储，留给确认后的规则计算。
- `attacks[].skill` 引用 `skills` 键；伤害 `base` 与 `add_damage_bonus` 分开记录。`needs_review` 的原始字符串不能直接执行。
- `quantity: null` 表示未知；一整套工具不自动展开内部数量，未知弹药不等于无限。
- `placement: owned_asset` 表示拥有资产，不代表当前随身携带。
- `special_effects.status: requires_runtime_implementation` 只是特例说明，不表示已有执行工具。例如手铐钥匙概率不覆盖锁匠技能。
- 攻击栏出现武器，不代表装备表明确发放该武器。

杰西卡的徒手伤害、格里的历史／图书馆括号值等保存在疑点记录中。现有资料还有待单独复核事项，例如大卫手铐的“数量／双”表达；不能仅因 `source_issues` 为空就认定没有转录问题。本文不修改或裁定这些数据。

## 6. NPC／生物随模组保存

《岭下暗影》的 `characters.yaml` 使用另一种结构：

```text
characters
├── josh                # 乔什·文斯考特，具名 NPC
├── ssyaa_hrisss         # 斯西亚·瑞斯，具名 NPC
├── degenerate          # 退化人模板
└── ghast               # 妖鬼模板
instances
├── ghast_1             # 引用 ghast
└── ghast_2             # 引用 ghast
groups
└── trained_assistants  # 引用 degenerate，定义数量
```

条目包含数值、技能、行为、来源、初始／阶段说明等。实际伤势、当前位置和命运应由未来本局状态管理，不把游玩变化写回模板。数值约定同时参考模组 `rulings.yaml`，不能只读旧原文。

`presentation.sprites.base` 引用同包 `assets/index.yaml` 的素材 ID。每类一张基础透明立绘，多个生物实例复用；没有表情、受伤或服装变体，变化由叙述表达。NPC 立绘与调查员头像的展示用途不同，不共享文件格式约定。

## 7. 当前前端如何使用人物

选择页经 `api/investigators.ts` 的 `listInvestigators` / `getInvestigator` 获取展示资料；它们目前通过真实 GET 获取后端 YAML／Markdown 投影。游戏预览沿用所选真实人物展示资料，动作仍为固定演示。

| 后端模板概念 | 客户端展示形式 |
|---|---|
| 身份 | `id`、`name`、`displayName`、`occupation`、`age` |
| `assets.portrait.file` | `portrait.url`；使用限定人物头像 GET 路由 |
| 八属性 | `attributes`，允许未知值 |
| 开局资源与上限 | `resources` 中 HP／MP 当前值和上限、SAN、幸运 |
| 技能映射 | `skills[]` 的名称、数值、主要技能标记 |
| 背景 Markdown | `background[]` 展示段落，后端按二级标题提取纯文本，空白项为 null |
| 装备与现金 | `equipment[]`、`cash`，区分 carried / owned |

上述投影已实现；假人物数据与假头像图集已移除。嵌套物品展开时保留容器名称，单位与未知参数保留在 note；不补全原卡数值或执行物品特例。

后台原卡、背景、裁切头像和来源资料不得直接打包进前端或整体静态公开。已实现 API 返回明确发布的摘要、详情及头像 URL；来源疑点、服务器路径和模板全文不属于人物目录摘要。

## 8. 模板与游戏实例分开

| 数据 | 生命周期 |
|---|---|
| 调查员 YAML／背景／头像 | 只读、版本化模板 |
| NPC／生物定义及立绘 | 模组只读资产，随内容版本维护 |
| 玩家填写、当前 HP／SAN／MP、装备消耗、NPC 本局状态 | 未来游戏实例，绑定模板／内容 ID、版本及开局快照 |
| 当前网页选择、消息、线索 | React 内存，刷新重置，无真实存档 |

当前没有新模板自动实例化流程。既有 CLI Excel／SQLite 链路独立存在，选中人物并不创建后端角色或游戏。

维护时保持目录 ID、文件 `id`、附件路径和背景锚点一致；改模板数值需更新内容版本、复核疑点。另见[调查员格式说明](../backend/data/characters/README.md)、[角色卡导入 Skill](../skills/coc-character-card-import/SKILL.md)、[模组存储结构](module-storage.md)、[用户旅程](user-journey.md)与[调查员适配契约](investigator-api.md)。

## 网页人物实例

2026-10-24：创建调查时按真实人物模板初始化当前资源、属性、技能、随身物品，并将完整公开初始快照与模板版本/hash写入本局JSON。缺失技能使用trpg现有基础值表；拥有资产只作人物档案展示，不自动当作随身工具。游戏只修改本局资源和背包，永不回写模板。十位人物均已验证可初始化、两局相互隔离。
