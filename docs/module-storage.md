# 模组存储结构

更新日期：2026-10-24。说明实际落盘的内容包及与前端的关系；字段细节以当前文件和[包说明](../backend/data/modules/darkness-beneath-the-hill/README.md)为依据，网页运行配置格式另见[模组运行配置](runtime-profiles.md)。

## 1. 存储位置

模组位于 `backend/data/modules/<module-directory>/`。当前主要内容包为《岭下暗影》，包含来源正文、实体、规则裁定、素材及制作记录。它是服务端只读资料，不是每局存档，也不是可直接发送给玩家的 JSON。

```text
backend/data/modules/darkness-beneath-the-hill/
├── manifest.yaml                   # 清单、入口、版本、能力与权限
├── README.md                       # 包说明
├── story.md                        # 来源正文与稳定锚点
├── characters.yaml                 # 本模组 NPC／生物、实例和群组
├── locations.yaml                  # 地点、粗粒度路线、门禁与背景引用
├── clues.yaml                      # 发现途径、玩家事实、Keeper 解释
├── objects.yaml                    # 场景物件和装置
├── events.yaml                     # 触发、结果和关联实体声明
├── endings.yaml                    # 结局维度、后日谈与奖励依据
├── keeper-options.yaml             # 可选主持安排，默认关闭
├── issues.yaml                     # 来源疑点与处理状态
├── rulings.yaml                    # 规则基线和显式项目裁定
├── adjudication-guide.md           # 裁定阅读说明
├── visual-style.yaml               # 统一画风与尺寸
├── asset-plan.yaml                 # 计划、提示词、验收和指纹
├── visual-preview.html             # 本地分层素材审阅工具
├── visual-validation.json          # 校验记录
├── checks/
│   ├── validate_rulings.py          # 独立只读内容检查
│   └── validate_rulings.py.lock
└── assets/
    ├── index.yaml                  # 素材 ID → 文件／正文引用／权限
    ├── source-text.txt             # 从已保存正文恢复的派生来源文本
    ├── *.png / *.webp              # 原书附件、背景、透明立绘等
    ├── sample-prompts-v1.json
    ├── visual-approval-history-v1.json
    └── adjudication-history-v1.json
```

素材统一存入 `assets/`，没有强制的地图／背景／立绘子目录。用途由索引和实体引用表达，不由文件夹名推断。

## 2. 清单、标识与版本

| `manifest.yaml` 字段 | 当前值／含义 |
|---|---|
| `id` | `darkness_beneath_the_hill`，内容包标识 |
| `schema_version` | `0.1.0`，现有草案格式版本 |
| `content_version` | `0.2.0`，内容与裁定版本 |
| `entry.location` / `entry.event` | `winscott_house` / `meet_josh` |
| `rules.edition` | CoC 7e；具体采用值见裁定文件 |
| `rules.profile` / `profile_sha256` | 项目裁定标识与摘要绑定 |
| `files` | 正文、实体、素材索引、画风、计划、裁定等入口 |
| `presentation.default_background` | `default_atmosphere`，素材 ID |
| `access.default` / `static_publication` | `keeper_only` / `false` |
| `runtime_compatible` | `false` |

前端目录 ID 为 `darkness-beneath-the-hill`，与清单 ID 的下划线写法不同。目录名、清单 ID 和前端公开 ID 不能直接混用，发布清单 module-catalogue.json 已显式映射三者，不依靠字符串替换推断。

`capabilities` 独立标记能力：内容审阅和视觉素材为 true，运行适配、事件执行、法术执行、单人游玩测试为 false。内容通过检查或疑点 resolved 不等于运行就绪。

## 3. 实体与出处如何关联

各 YAML 通过稳定实体 ID 关联，例如事件引用地点、人物、线索或物件；`source` 保留结构化记录与正文出处的联系。

| 引用形式 | 解析基准 |
|---|---|
| `manifest.files.*`、`source.document` | 模组根目录 |
| `source.anchor` | 对应正文中的稳定 HTML 锚点 |
| 素材索引的 `file` | 模组 `assets/` 目录 |
| 文字展示材料的 `content_ref` | 来源文档和章节，按约定读取正文 |
| `presentation.background` / `sprites.base` | 素材 ID，先查索引，不直接拼路径 |

正文保留来源事实，`rulings.yaml` 记录核实依据、项目裁定和限制措施，`issues.yaml` 保留原问题及解决方式；不能让模型临时改写数值来解决冲突。

地点连接是显式的粗粒度场景抽象。高差、危险、笼门、传送仍须执行器处理，连接不能直接视为无条件移动许可。`events.yaml` 的 `execution: descriptive_only` 表示触发和骰子表达式尚非可执行 DSL。

`endings.yaml` 是后端结果依据；前端结案只需要结束标志和最终 Keeper 叙述，不应读取整份隐藏结局表。

## 4. 展示素材的存储与引用

实体保存展示引用。例如以下是住宅与乔什条目中的节选，不含本局变化：

```yaml
# locations.yaml 的地点条目内
presentation:
  background: bg_winscott_house

# characters.yaml 的 josh 条目内
presentation:
  sprites:
    base: sprite_josh_base
```

`assets/index.yaml` 记录文件／正文引用、标题、媒体类型、SHA-256、来源、关联实体、标签与访问条件。生成图还保存尺寸、alpha、画风版本、生成与验收指纹。

当前索引共 34 项：7 张原书图片、2 份正文展示材料、25 项已验收生成素材。生成素材为 1 张模组封面、1 张默认背景、19 张场景背景、4 张基础透明立绘；旧尝试图片和历史 JSON 不自动成为可展示素材。

| 素材 | 当前约定 |
|---|---|
| 背景 | `1920×1080 WebP`，不含人物，与立绘独立 |
| NPC／生物 | `1024×1536 PNG`，真实透明通道，每类一张 `base` |
| 同类生物实例 | 复用模板立绘，不按实例重复制图 |
| 竖版模组封面 | `presentation.cover: module_cover`；文件 assets/module-cover-v1.webp；发布清单 coverAsset 明确授权，封面 GET 按索引返回，不公开整包 |

多个地点可以共享背景。图片不能决定路线、物件数量或已发生事件；图中陈设不自动成为剧情事实。两张身份未确认的建筑参考图仍禁止自动按具体建筑展示。

`asset-plan.yaml` 保存制作及复核过程，`visual-style.yaml` 保存画风约束；它们和历史归档不下发给玩家。原始文本附件缺失，`source-text.txt` 是派生文本，清单同时保留原附件摘要与恢复说明，不宣称原附件字节已恢复。

## 5. 前端当前使用什么

网页目录已通过真实 GET 读取显式公开引言与 manifest 标题，调查员通过真实目录接口读取。游戏经api/game.ts接入真实HTTP／SSE，执行独立MVP配置；完整内容包本身仍不是可执行配置。

早期开场预览保留以下两张静态副本，当前正式游戏不再引用：

| 模组资源 | 前端静态预览 |
|---|---|
| `assets/bg_winscott_house-v1.webp` | `frontend/public/images/game-preview/winscott-house.webp` |
| `assets/sprite_josh_base-v1.png` | `frontend/public/images/game-preview/josh.png` |

这是用户指定的开场预览允许清单，不修改原模组 `keeper_only`，不构成整包公开授权。正式游戏已返回本局授权的素材URL；按既有决定暂保留静态副本，不将 `backend/data/modules/` 整体挂为静态目录。

玩家检索先按本局、接收者和已揭示事实过滤，再搜索。授权前隐藏标题、摘要和缩略图也不得泄露；地图原图不直接给玩家，探索图需单独处理。

## 6. 内容与本局状态分开

| 数据 | 归属 |
|---|---|
| 正文、NPC 模板、地点、裁定、图片索引 | 当前只读内容包 |
| 当前位置、已揭示事实、HP／SAN、检定与结束状态 | 本局JSON，绑定内容版本与指纹，不写回内容包；不实现自由计时器 |
| 完整网页消息和线索 | 本局JSON持久化，刷新通过GET恢复 |
| 既有 CLI 存储 | 独立SQLite适配，与网页JSON存档隔离 |

CLI 仍使用 `backend/data/campaign.json` 和 `backend/data/scenes/*.json` 等运行配置。该 YAML 包不能直接传给当前 `--campaign` 加载器，目录完成不代表兼容运行时。

## 7. 维护与只读检查

增加模组使用独立目录和清单入口，保持 ID、出处锚点、素材引用和版本一致。来源／裁定变化后复核摘要与素材指纹，不仅修改图片文件名。

从仓库根目录可运行，不会执行游戏或调用模型：

```sh
uv run --locked --script backend/data/modules/darkness-beneath-the-hill/checks/validate_rulings.py
uv run --locked --script skills/coc-module-builder/scripts/validate_module.py backend/data/modules/darkness-beneath-the-hill --complete
```

检查证明内容和素材记录一致，不证明执行器、法术或单人游戏完成。另见[包说明](../backend/data/modules/darkness-beneath-the-hill/README.md)、[裁定交付记录](design/done/darkness-adjudications.md)、[人物存储结构](character-storage.md)、[用户旅程](user-journey.md)。

## 网页MVP运行配置

2026-10-24首版新增 `backend/data/runtime/darkness-solo-mvp-v1.json`（新局现为v4，v1只用于兼容），独立于原内容包。目录发布清单的runtimeProfile绑定darkness-solo-mvp。配置引用原场景与素材，但单独定义简化事件／前提／普通检定／损失与重复策略；完整包manifest的runtime_compatible:false继续表示原包不能被当成全面可执行模组。开局保存配置hash及原包版本，更新不兼容时显式报错。正式游戏资产通过game_id素材接口按已进入场景授权，原data目录不静态挂载。

## 8. 网页可执行配置

原始内容包与每局状态之间增加独立的schemaVersion=2配置。`data/runtime/index.json`按公开moduleId与runtimeProfile显式登记当前文件；当前`darkness-solo-mvp-v4.json`记录场景、NPC、可见目标、挑战、条件／效果及结案，旧v2／v3以固定指纹保留，原v1用于兼容识别。Python只解释通用工具，不按模组名、NPC名或场景名分支。

现有原文包不能仅靠加入目录就自动游玩，需要整理为受支持的运行配置并验证。已有机制的新模组无需改Python；复杂新机制仍需通用能力实现。接入、私有数据边界和旧存档升级见[运行配置说明](runtime-profiles.md)。

## 调查内容发布版本

当前新开局使用 `data/runtime/darkness-solo-mvp-v4.json`（4.0.0，调查扩充与目标交互版）。十一场景、线索和地窖工具箱动作由配置驱动；原完整模组内容包与素材不变。`runtime/index.json`以current选择新局配置，以retained固定哈希保留旧v2／v3，v1兼容仍只升级到v2。已有game_id不会被切换到更长的新剧情，详见[运行配置](runtime-profiles.md)及[调查扩充](design/done/darkness-investigation.md)。
