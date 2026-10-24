# 内容包格式与视觉扩展

## 版本、命名与布局

核心 schema_version 为字符串 '0.1.0'，沿用现有声明式内容格式；新增 visual_format_version 为 '0.1.0'，不是游戏 API。未来格式改变需显式升级，不静默迁移旧包。ID 使用 snake_case，目录 slug 使用 kebab-case；实体 ID 在各实体集合间唯一。素材 ID 同时作为制作计划 ID；实体 ID 与素材 ID 可不同。

固定模板清单（无内容的集合保持 {} 或 []）：

    manifest.yaml
    story.md
    characters.yaml
    locations.yaml
    clues.yaml
    objects.yaml
    events.yaml
    endings.yaml
    keeper-options.yaml
    issues.yaml
    visual-style.yaml
    asset-plan.yaml
    assets/index.yaml

manifest.files 使用 story/characters/locations/clues/objects/events/endings/keeper_options/issues/visual_style/asset_plan/assets 指向上述文件。目录位置不决定媒体语义或访问权限，附件可放 assets/ 任意安全相对子路径。所有内部路径必须留在模组根目录；索引 file 另以 assets/ 为基准。不允许绝对路径、..、反斜线路径或符号链接逃逸。

manifest 必填 id/title/original_title（可 null）/schema_version/content_version/status/language/runtime_compatible；status 为 authored_draft，runtime_compatible 为 false。players 保存推荐人数和 solo_requires_adaptation；setting 保存时期与城市；entry.location/event 引用真实实体，无入口时为 null；rules.system 固定 Call of Cthulhu，edition 未知为 null 且 issue 引用待确认项，external_dependencies 为字符串列表。access.default 固定 keeper_only，static_publication 为 false。source.document 指向包内保存的原始 UTF-8 正文附件，source.text_sha256 为其原始字节 SHA-256。state_policy 说明定义只读、本局状态另存、索引可重建。content_version 变化代表来源或提取内容变更，视觉修订另记版本。

## 来源保真与通用字段

先将用户提供的文本按原始字节保存为 assets/source-text.txt（非文本源保留原件并另外存 UTF-8 转录）。story.md 仅把换行统一 LF、插入独立一行的 <a id="stable-id"></a>；不清理页眉、标点、译注和留白。记录转录/OCR 疑点，不把转录宣称为字节保真。去掉插入的锚点后应与 source.document 经 CRLF/CR→LF 后相同。若原文已有同形锚点，先记录为 issue，选择不同锚点形式和人工保真核验，不擅自删除原文。

有内容的实体必须包含 source: {document: story.md, anchor: stable-id}；同一条提取多个出处可用 sources 列表。origin 可为 extracted/adaptation/house_rule，未写默认 extracted；改编与房规必须写明，并与原文事实分开。通用 issue 字段引用 issues 中 ID。事实未知用 null，不能填零、空字符串或模型常识代替未知量。

source 与 content_ref 的 document 相对包根，anchor 必须唯一可定位。content_ref 引用锚点起至下一章节锚点，不复制第二份展示材料。图片是否可展示取决于未来本局事实，不由检索命中决定。

## 各配置完整职责与结构

| 文件/顶层集合 | 字段与约定 |
|---|---|
| characters: characters | 具名 NPC 或 creature_template。name、kind、source 必填；attributes、stats、skills 用映射，武器 weapons 为列表；initial 保存初始地点和状态，phase_notes 保存阶段说明，不存本局变化。人物未知值 null；不执行表达式。|
| characters: instances/groups | instances: {id: {template, source, ...}} 记录独立实例；groups: {id: {template, count, source, ...}} 记录群体，count 未知可 null。template 指 creature_template 的 ID，实例状态仍在未来存档。|
| locations: locations | name/source；parent 可引用父地点；map_ref: {asset, label} 或 map_refs 列表；detail_map 指素材 ID。区域总称可作为地点，但不是额外场景图。|
| locations: connections | [{id, from_location, to_location, bidirectional, source, via_object?}]；原文未确认的连接不登记为确定事实。|
| locations: map_features/topology_review | map_features 为 {id: {asset, label, clue? 或 object?}}，区分房间、线索与障碍；topology_review 保存审阅状态、issue 与 notes。|
| clues: clues | name/source/locations 列表/acquisition 列表/player_fact；keeper_fact 可选，不能对玩家直接投影；asset 指索引中的展示材料；optional_relocation 引用主持选项。发现、理解、展示是不同状态。|
| objects: objects | name/kind/location/source，按需 description、rules、states；唯一装置只定义一次，其他配置引用其 ID。|
| events: events | 文件 status: authored_draft、execution: descriptive_only、policy 列表；每项 source/origin/trigger 必填，可有 location、clue/clues、object、target、requires、check、on_success/on_failure、delay、repeat_policy、note。trigger/结果可保留提取文本；不把它们宣称为统一可执行 DSL。未知重试/时长/损失登记 issue。|
| endings | source 可空；outcome_dimensions/epilogues 列表、reward_policy 映射；rewards: {id: {source, condition, san_gain/san_loss 等}}。奖励表达式不执行，互斥组 exclusive_group 和上限按来源保存；重复结算由未来执行器处理。|
| keeper-options: options | {id: {origin: source_optional, enabled: false, source, description, ...}}；可选不等于每局发生，不暗中启用路线封闭等安排。|
| issues: issues | {id: {status: open/resolved, blocks_runtime: bool, source, description, resolution?}}；解决需保留依据，不能简单删掉未决事实。|
| assets: assets | 索引格式见下节，文字展示材料使用 content_ref，二进制使用 file，二者互斥。|

不要求把所有行为压成有限选项；未预写的合理行动由未来 Keeper 提议、程序验证、记录本局裁定。制作 skill 仅整理来源，不执行该路径。

## 素材索引与展示引用

assets/index.yaml 顶层 format_version: '0.1.0'、path_base: assets/、policy 与 assets 映射。原始附件保持原字节，二进制项必填 file/title/media_type/sha256/source/relates_to/tags/access。relates_to 是实体 ID 列表，不能改成分类映射。文字材料改用 content_ref；不要求 sha256。source 可追溯 story 锚点和原附件名称。

access: {default: keeper_only, player_reveal_fact: null 或稳定事实ID}。事实 ID 是未来授权契约，不需要与实体 ID 同名，也不代表权限已经实现。原始秘密地图的 player_reveal_fact 保持 null。无剧情的默认背景也维持默认拒绝，由未来展示层显式选择；不引入未经实现的 player_safe 权限枚举。

新增字段：kind 可为 module_cover/scene_background/default_background/npc_sprite/creature_sprite/handout/reference/original；visual_format_version: '0.1.0'；width/height 为实际像素，has_alpha 为实际通道信息；anchor 为 [x,y]、范围 0..1，默认人物 [0.5,1.0]。background 的 focus 为 [x,y]、默认 [0.5,0.5]，不是线索定位。

生成项另有 generation: {plan_id, style_version, content_fingerprint, input_fingerprint, tool, artistic_additions, review: {status: accepted, note}}。完整 prompt/references/attempts 保存在 asset-plan，不向前端发送。新图人工验收后才写索引，且记录必须与当前计划一致。已有出版物图片不要求改尺寸，也不因为画风不同而修改原件。

manifest.presentation.cover 引用 module_cover 素材 ID，供模组库卡片使用；封面为 1024×1536 不透明 WebP，无文字/UI/边框，只表现玩家引言可知内容，默认仍为 keeper_only，公开投影另行实现。manifest.presentation.default_background 指计划或已验收背景 ID；locations.<id>.presentation.background 同样指 ID，不配置则回退默认；characters/instances/groups 的 presentation.sprites 保留映射结构，仅使用 {base: 素材ID}。每个 NPC/生物仅制作一张基础立绘，生物实例与群体复用模板基础图；情绪、受伤及剧情状态通过文字表达，不规划状态变体。多个地点直接引用同一背景，避免复制文件。阶段中允许引用未完成计划，但此时不能视为可展示；--complete 要求这些素材都已验收。引用不存在的计划/素材是错误。默认背景必须登记为 default_background。

## 视觉制作记录

visual-style.yaml：visual_format_version、style_id、version、status: draft/approved、approval_note、references（包内路径列表）、medium、palette、lighting、era、composition、sizes。approved 必须是用户已选定风格的真实记录；不能由校验器或 agent 自称用户批准。

asset-plan.yaml：visual_format_version、content_fingerprint（当前正文、原来源及非视觉内容配置的规范指纹）、image_tool: available/unavailable、items 映射。每项字段：

- kind、relates_to、status: planned/blocked_tool/review/accepted/failed、batch: sample/later。
- output（相对 assets/ 的版本化目标路径）；size: [宽,高]；style_version、prompt（最终完整文本）、references（包内路径列表）、reuse_of（另一计划 ID 或 null）。复用项只能指相同 kind、尺寸和 output，不重复生成，不形成环。
- input_fingerprint：校验器计算的当前输入指纹；attempts 为 [{tool, outcome: review/failed/accepted, note}]，最多三条，即初次加两次修正。
- review 状态结果可以有 candidate_file/sha256；这些候选不进入索引；accepted 需有对应的索引项，复用项共享文件但各有索引记录。

content_fingerprint 由随附校验器生成：取 manifest（排除 files/presentation）、八份核心 YAML（递归排除 presentation）、story 全文与原始正文 SHA-256，组成 manifest/documents/story/original_sha256 映射并规范 JSON 后计算 SHA-256。presentation 不影响剧情指纹，但对应图片计划的输入指纹单独追踪；不需要因更换背景引用重新生成所有图片。

input_fingerprint = SHA256(canonical JSON({id, kind, output, size, relates_to, style_version, prompt, references:[{file,sha256}], reuse_of, content_fingerprint, style_file_sha256}))。UTF-8、ensure_ascii=False、sort_keys=True、separators=(',',':')。不手写随机指纹。参考路径需存在，图像参考使用前先看图；本 skill 不捆绑任何出版物参考图。

校验器返回可复制的当前指纹和各项建议。记录是 agent 在得到实际结果后写入的，校验器永不修复或覆盖资产。旧风格与内容版本可留档；当前验收失配项列 revise，不自动视为 accepted。

这套校验器面向带视觉扩展与包内原始来源的新制作包，不是旧模组自动迁移器。仅有核心配置的旧包先离线盘点；缺原始来源或视觉记录时报告缺项，在用户要求补齐时再新增，不直接改写已有内容包。
