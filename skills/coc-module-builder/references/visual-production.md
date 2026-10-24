# 统一风格的视觉生产

## 先建立风格与素材计划

读取模组时代、地点、人物和已揭示事实，不把秘密总图作为公开背景。先盘点原素材：原图保留，生成图属于独立艺术解释。场景分专属、共用、默认三种，不按地点数机械生图。每个 NPC 和生物只制作一张基础透明立绘，不生成表情、受伤、服装或剧情状态变体；这些变化由对话和文字表达。生物实例复用模板基础图，不因每个实例都生成新脸。修订不合格基础图仍遵守原有重试与版本规则。

visual-style 使用模板中的写实绘画、克制色彩、可读暗部为默认。统一笔触与细节密度，时代/服饰/建筑/地貌来自来源。黑金是应用 UI 风格，不要求把世界里的全部物件染成黑金。每个包独立存风格与参考文件，不引用另一台电脑上的已安装 skill。

默认 sample 集合恰为：一张模组竖版封面、一张无剧情默认背景、一张入口场景背景、第一位实际出场 NPC 的基础立绘。缺 NPC 时不创造人物，标明不适用。只用这四项样本建立视觉方向；其余项 batch: later。用户选择样本后将风格状态记 approved 并填写选择依据，再进入继续生成。已选参考直接复用，不重复询问。

## 规格与构图

| 类型 | 验收交付 | 必须检查 |
|---|---|---|
| 模组封面 | 1024×1536、不透明 WebP | 供模组库竖卡裁切；主题集中，上部留标题叠加空间；不带文字、UI、边框；仅用玩家引言可知信息，不暴露隐藏人物、生物或结局 |
| 背景/默认 | 1920×1080、不透明 WebP | 不带人物、文字、边框、按钮；中部建筑结构清楚，左右留立绘空间，底部允许对话遮挡 |
| 人类 NPC | 1024×1536、透明 PNG | 头顶至大腿，四周约 5% 留白，头/双臂/衣物边缘完整；默认落点 [0.5,1.0] |
| 生物 | 1024×1536 竖幅或 1536×1536 方幅、透明 PNG | 按真实体型选择，plan 明确尺寸与落点；不把巨大生物强裁成人形 |
| 原书展示材料 | 原始格式与尺寸 | 不修改内容、署名与字节；细节另开图查看 |

生成工具尺寸能力不同，以交付文件实际尺寸验收。只做明确的等比缩放、格式转换和透明留边可用通用图片工具，记录处理；禁止拉伸画面，禁止自动裁去人物四肢。改变内容、补画、去背景或修复透明边缘优先使用宿主图片编辑工具。无法获得合格规格就留 review/failed，不能改元数据假装符合。

背景不画 NPC，立绘不接触背景家具、不倚靠不存在的桌面，不带连接地面的投影；可携带来源允许的随身道具。采用柔和中性主光与一致轮廓光，不能强烈烘焙仅适用于某个房间的背景色。脸部一致性优先参考图编辑，不依赖所谓固定 seed 或相同文字就能保证身份。

默认背景低细节、抽象暗色空间/纸纹，不画门、桌子、怪物、秘密符号等具体事实。普通走廊不直接画出尚未发现的陷坑；发现前后用不同素材 ID 和揭示条件，不能靠前端隐藏文字来去剧透。

## 提示词组成

每次调用把以下各段展开为完整文本，最终文本写入 plan.prompt；不把“同上”“参考聊天记录”留给未来 agent。场景与人物模板只作为骨架，不能把未在模组中出现的人、家具或线索补成事实。

    Use case: historical-scene / stylized-concept
    Asset type: standalone game scene background
    Source facts: <当前可观察事实与出处锚点>
    Artistic additions: <不影响玩法的视觉解释；未知也明确说明>
    Style: <完整 medium、palette、lighting、era、细节规范>
    Reference images: <文件和角色：画风参考/场景参考>
    Scene: <建筑、材质、环境、时期>
    Composition: 16:9; character staging space; dialogue-safe lower region.
    Constraints: no people, no NPCs, no UI, no text, no secret clues before reveal.
    Deliverable: opaque WebP, 1920x1080 after inspection/export.

    Use case: stylized-concept / identity-preserve for edits
    Asset type: independent NPC sprite with real transparency
    Identity: <人物 ID、原文特征、服装；外貌补充单列>
    Style: <同一完整风格规范>
    Reference images: <基础立绘用 identity reference；其他图仅 style reference>
    Pose/expression: <符合人物设定的基础姿态与表情，双臂完整，与场景家具无接触>
    Invariants for edits: same face, hair, outfit, body scale, camera, canvas and position.
    Composition: head to upper thighs, 5% safe margin, bottom anchor [0.5,1].
    Constraints: no scenery, no floor shadow, no text, no frame, no checkerboard painted in.
    Deliverable: 1024x1536 PNG with genuine transparent alpha.

封面使用同一风格的场景模板，Asset type 改为 module library cover illustration，构图改为 2:3 portrait、主题集中、上部留标题叠加空间；交付为 1024×1536 不透明 WebP。只取玩家引言可知的场所与氛围，不透露秘密；标题、编号、标签、边框由前端叠加。已有合格封面优先复用，不重复生成。封面虽用于选择页，包内默认权限不因此自动公开。

默认背景使用相同场景模板但明确 abstract/non-location-specific/no identifiable objects。不得用“游戏截图”生成素材，否则会把 UI 或人物画进去。

## 工具、记录与重试

先发现宿主可用的生图与编辑能力。Codex 的 imagegen 是首选，不要求 API key；其他宿主使用实际可用的同类工具，不假设其名称。工具不可用时 image_tool: unavailable、待生图项 blocked_tool；完整保留 prompt 和计划，报告完成的是整理与规划，不是首批样本。

对本地参考先查看。调用时明确每张图的角色；透明请求显式设置工具透明选项，若无透明能力则标明限制，不用白色/棋盘格冒充。生成后检查文件，完整记录 tool/outcome/note；总尝试次数最多 3，达到上限不重新调用。批量仍逐项追踪，不复用一个结果冒充多个不同素材。

为每项记录当前 content_fingerprint/style_version/input_fingerprint；校验命令的 JSON 输出提供规范指纹。首次生产前可先将指纹从报告写回计划再执行。style 的参考更新会使旧项变 revise；把用户已选定样本另存稳定 reference 文件，更新风格后以实际已接受图重新核验记录，不能忽略失配警告。

candidate 图保存到 assets/ 的新版本路径，review 完成才写入 index。不要把工具返回的私有绝对路径持久化为引用。记录不包含 API key、请求令牌或用户无关私密信息。新版本用 -v2 等后缀，不覆盖已验收项；保留旧文件，不再使用的记录可从当前索引移出留在制作历史。

## 人工验收与合成

检查：剧情事实与时代、人物身份/服装一致性、手与边缘、画风/光向、危险/秘密是否提前暴露、PNG 是否真透明。自动尺寸/alpha 检查无法识别这些问题。

用已生成文件进行合成，不再为“合成图”调用生图工具。有网页环境用临时 HTML/CSS：背景 object-fit: cover，NPC 绝对定位独立层，对话遮挡底部约 25%；至少比较 16:9 与更宽场景裁切。没有浏览器时可用本地图片合成，仅供 QA，不伪称真实网页验收；宿主不支持合成则明确该项未验证。

样本通过后报告可查看文件与预览，等待用户选定风格；继续生产前检查实际选择记录。人物与背景只是表现，不能根据图中物件数量或手势修改事件、检定或本局状态。
