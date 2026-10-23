# CoC 人物模板格式 1.0

本文件是完整输出约定。所有资料从输入图片转录；示例人物为虚构，仅说明结构，不能作为未提供数值的默认值。不需要其他项目或运行引擎。

## 目录、身份与版本

一个人物一个目录：`<root>/<id>/character.yaml`、`background.md`、可选 `assets/portrait.png`。无 manifest；附件索引内嵌在 YAML。发布前禁止覆盖已经存在的角色目录，包括同名空目录或符号链接。

ID 使用小写 ASCII 字母、数字、下划线或连字符，首字符为字母/数字；是内部标识，不必猜测人物英文原名。同一批和目标根目录中必须唯一，且与目录名一致；多页同一人物不重复建目录。

schema_version 固定字符串 "1.0"。新模板 version 固定字符串 "1.0.0"；后续修改版本需另行授权，不在本导入流程自动修改旧模板。

## character.yaml 字段

除标记“可选”的字段外均须存在。数值字段必须是 YAML 整数，不能用百分号字符串或布尔值。缺失/不清楚的必填数值用 null，同时在 source_issues 给出对应的 field 和解释；不以零代替未知。

| 字段 | 类型与含义 |
|---|---|
| schema_version / version | 字符串，分别是格式/内容版本 |
| id / name | 非空字符串；无法确认姓名时该人物未完成，不虚构 |
| age | 非负整数或带疑点说明的 null |
| occupation | 非空字符串或带疑点说明的 null；不是技能生成器 |
| aliases | 可选，非空字符串列表，仅存卡面给出的别名 |
| background | 固定 background.md；人物正文唯一维护处 |
| source | 映射，description 为非空来源说明；可选 image_number 为正整数，标识用户所给图片序号 |
| source.pages | 可选，非空映射列表；每项 label 为非空页标识，可选 image_number；多页来源写在这里，不复制原卡 |
| assets | 映射，以素材 ID 为键；无头像时可为空映射 {} |
| attributes | 必须含 STR、CON、SIZ、DEX、INT、APP、POW、EDU 八键，各值非负整数或带疑点说明的 null |
| initial_resources | hp、san、mp、luck 四键，各值非负整数或带疑点说明的 null，表示卡面初始资源 |
| authored_derived | hp_max、mp_max、mov 非负整数或带疑点说明的 null；build 为整数或 null；db 为骰子表达式字符串或 null |
| skills | 映射，非空技能名→非负整数；允许超过100，不存困难/极难值。无法辨认某项值时省略该条并记录疑点；未列技能不是0 |
| attacks | 攻击映射列表，无攻击为 []，见后文 |
| starting_equipment | 装备映射列表，无装备为 []，见后文 |
| starting_money | currency 为非空货币代码；amount 为非负数字或带疑点说明的 null。币种未知用 currency: unknown，并记录疑点 |
| customization | 映射列表，可填写栏目，见正文锚点；没有可填写项为 [] |
| source_issues | 映射列表，每项 id、field、status、note；source_text 可选字符串/null。无疑点为 [] |

source_issues 每项 id 在人物内唯一，field 是字段位置（如 attributes.STR、skills.历史、attacks.unarmed.damage、assets.portrait）；status 固定 needs_review；note 是具体解释。原卡文本可记录在 source_text 中，无法辨认时为 null。常规可选装备参数为 null 已足以表示未知，不强制每个未知数量另建疑点；必填数值、缺头像或原文矛盾则需记录。

保留原卡值，不按规则重算。仅明确为满资源的起始预设卡可将卡面 HP/MP 同时记录为对应上限；受伤角色或未明确上限时填 null 并说明。SAN 没有明确上限就不添加该字段，初始 SAN 不等于必须取 POW。

技能名称仅做明确的展示同义归一：躲闪/闪躲→闪避、艺术/手艺→艺术与手艺、领航→导航。专长保留，如科学（生物学）、语言（法语）、手枪（.22）；不得把不同专长或心理学与精神分析合并。未辨认的词保留原文并记录疑点，不自动翻译成推测技能。

卡面可明确识别为排版或脚注的百分号、星号不属于规范技能名；有待查脚注时把原始写法和星号说明缺失记入 source_issues。对疑似错字或模糊字先局部放大复核，不能把首次 OCR/视觉识别结果直接称为原文。

### 附件

assets 各项含 file、media_type，可选 description。portrait 的 file 固定 assets/portrait.png，media_type 固定 image/png；其他附件可按需增加并使用相对路径。
所有附件路径必须位于该人物目录内部，不允许绝对路径、`..`、URL 或任何路径组件为符号链接。索引不赋予公开访问权限。

无头像时 assets 不声明 portrait，并添加 field=assets.portrait 的 source_issues。不得生成占位人物图。

### 攻击

每项含唯一 id、非空 label、skill（必须精确引用 skills 的一个键）、damage 映射。不复制攻击命中率，不自动授予武器。

普通 damage 含 base（如 1D3、1D6-1、2D6）、add_damage_bonus（布尔）。原卡明确加 DB 时 base 只记录基础骰，布尔为 true；固定伤害不额外加 DB。db 可为 "0"、"-1"、"+1D4" 等；只存表达式，不执行字符串。

冲突时保存：

```yaml
damage:
  base: null
  add_damage_bonus: null
  source_expression: 1D3+1D6
  status: needs_review
```

同时用对应攻击路径的 source_issues 保存冲突依据；这个 damage 不能视为可执行。缺攻击技能值时省略该攻击并记录疑点，不捏造 skill 或数值。

### 装备、现金与特例

每项含唯一 id、非空 name、quantity（正整数或 null）。成套物品 quantity=1 指一整套；数量未给出则 null，不代表无限。嵌套 contents 为同结构列表；物品 ID 在整个人物的装备树中唯一。

可选字段：

- unit：非空单位，如 双、小撮。
- placement：owned_asset 表示汽车等拥有资产；非随身携入场景的默认许可。未标记的物品为初始装备，实际携带由开局确认。
- contents：明确列出的工具包内容；未列明时用 contents_unspecified: true，不补造 contents。
- details_unspecified：布尔，原卡缺乏具体型号等详情。
- ammunition：非负整数或 null；licensed：布尔或 null。
- length：映射，value 为非负数字，unit 为非空单位，整项未知可为 null。
- combat_profile：可为 null，表示原卡没给出该物品的攻击资料。
- container：非空字符串，原卡给出的容器说明。
- special_effects：列表，每项 id、description、status（requires_runtime_implementation）；可含 success_chance_percent（0到100数字）及 target（非空字符串）。这些是物品特例说明，不实现游戏效果、不替换角色技能。

现金单独存 starting_money，不能从信用评级换算。背景中的宝贵之物不自动加入 starting_equipment。不要从攻击栏反向补发一件装备；有差异则记录疑点。

### 背景正文与可填写栏目

background.md 以人物名字为一级标题；七个二级栏目用以下稳定锚点。正文保留原卡措辞、人物关系及译注；不得补写性格、信念或创作故事。

| 栏目 | 锚点 |
|---|---|
| 个人描述 | appearance |
| 特质 | traits |
| 思想与信念 | beliefs |
| 重要之人 | people |
| 意义非凡之地 | places |
| 宝贵之物 | treasured |
| 人物经历 | history |

使用 `<a id="beliefs"></a>` 形式。原卡留白写“（原卡留空，供玩家填写。）”；未提供写“（原卡未提供此栏目内容，供玩家填写。）”；看不清写“（原卡此处无法辨认，待确认。）”并记录疑点，不能称为留空。

customization 的每项 section、anchor 为上表相同的栏目键，editable 为 true；仅列明确留空或未提供内容的栏目。无法辨认的固定内容是疑点，不擅自转成可自由创作项。固定正文不在 YAML 再保存副本。

## 虚构示例：一位档案研究员

以下不是任何输入的默认角色。示例含完整 YAML 和背景；头像必须另从真实输入裁切，无头像则按前述规则省略。

```yaml
schema_version: "1.0"
version: "1.0.0"
id: lin_archivist
name: 林知秋
age: 32
occupation: 档案研究员
aliases: [知秋]
background: background.md
source:
  description: 用户提供的角色卡，第1张图片。
  image_number: 1
assets:
  portrait:
    file: assets/portrait.png
    media_type: image/png
    description: 原卡头像，保留相框。
attributes:
  STR: 50
  CON: 60
  SIZ: 55
  DEX: 65
  INT: 75
  APP: 50
  POW: 60
  EDU: 80
initial_resources:
  hp: 11
  san: 58
  mp: 12
  luck: 45
authored_derived:
  hp_max: 11
  mp_max: 12
  mov: 8
  db: "0"
  build: 0
skills:
  斗殴: 25
  闪避: 32
  图书馆使用: 70
  历史: 60
  语言（拉丁语）: 40
attacks:
  - id: unarmed
    label: 徒手斗殴
    skill: 斗殴
    damage:
      base: 1D3
      add_damage_bonus: false
starting_equipment:
  - id: research_bag
    name: 资料袋
    quantity: 1
    contents:
      - id: notebook
        name: 笔记本
        quantity: 1
      - id: pencils
        name: 铅笔
        quantity: null
  - id: handcuff_key
    name: 特制手铐钥匙
    quantity: 1
    special_effects:
      - id: open_ordinary_handcuffs
        description: 原卡注明有80%的几率打开普通手铐。
        status: requires_runtime_implementation
        success_chance_percent: 80
        target: 普通手铐
starting_money:
  currency: USD
  amount: 10
customization:
  - section: people
    anchor: people
    editable: true
  - section: places
    anchor: places
    editable: true
source_issues: []
```

对应 background.md：

```markdown
# 林知秋

<a id="appearance"></a>
## 个人描述

总穿着袖口磨旧的外套。

<a id="traits"></a>
## 特质

耐心，习惯核实每一条引文。

<a id="beliefs"></a>
## 思想与信念

记录值得被认真保存。

<a id="people"></a>
## 重要之人

（原卡留空，供玩家填写。）

<a id="places"></a>
## 意义非凡之地

（原卡未提供此栏目内容，供玩家填写。）

<a id="treasured"></a>
## 宝贵之物

祖母留下的一枚书签。

<a id="history"></a>
## 人物经历

她在地方档案馆整理旧报纸，偶尔替研究者查找失踪的记录。
```

## 检查与交付

对照原图检查所有数值和文本；校验脚本不能替代视觉校对。source_issues 保留的冲突不阻止结构有效，但不能宣称这些规则已经能够执行。
不复制运行时类，不添加项目 import 或绝对路径依赖。角色模板与本局状态独立；后续玩家定制、资源变化和物品消耗不覆盖这些文件。
