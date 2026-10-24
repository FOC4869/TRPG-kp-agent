# 当前上下文

2026-10-24：按用户要求提交当前工作（9dde42b），将全部既有开发工作合并到taosdev（6a2ef3f），保留210f535文档历史；五份文档冲突采用最新实现并保留旧记录。祖先检查确认25个本地分支端点均已纳入。冻结标签mvp-freeze-2026-10-24及[冻结说明](../releases/mvp-freeze-2026-10-24.md)记录可复现基线、验证和后续修复约定；人物／模组存储说明清理旧预览表述。推送范围限定为origin的taosdev、feat/common-actions和冻结标签；无新增模型调用、密钥或存档提交。


2026-10-24：完成常见自由行动。独立工作区feat/common-actions-work在原脏基线之上实施并校验，集成分支feat/common-actions；未自动commit/push。新增use_item/drop/give/confirm_action、持久危险确认、独立伤害effect卡/SSE和声明式实体actions。common-actions-v1按原始装备ID冻结能力，大砍刀1D6/徒手1D3为明确MVP改编。当前v4增加地窖工具箱动作，v3保留原指纹；旧局只读补mechanics、不换剧情。修改Keeper提示词尊重玩家意图、简短回应，不伪造玩家自行收手；未支持动作仍需裁定，不能凭叙述修改状态。

验证：274项后端离线测试、内容校验（v4/v2/v3）、npm ci/lint/typecheck/build及四项适配检查；收尾26项相关回归通过。临时模拟Keeper桌面检查1440×900/1280×720，确认/取消/刷新/伤害/历史/陈旧按钮409恢复通过，原玩家局未作为测试输入。无新增付费调用；DeepSeek自然语言理解与新语气仍待真实试玩。集成后再次通过274项完整后端测试及全部前端门禁；后端PID34486，8000与Vite代理健康200，用户game_id读取200，19个真实存档/备份SHA256未改变。设计见[common-actions](../design/done/common-actions.md)，契约与能力边界见interfaces/runtime-profiles与ADR-0006。

2026-10-24：用户反馈游戏首轮“回应未完成”，排查确认密钥鉴权正常，实际为新版Plan的nullable工具内$ref分支被DeepSeek拒绝（400 anyOf missing type）。网页适配器展开本地引用、移除不支持的字符串长度约束，本地Plan仍严格验证；供应商认证／余额／限流／格式／网络错误改为固定公开分类，存档仅加安全errorCode。259项后端测试通过，新增6项实际Responses边界／脱敏／原请求恢复回归。原授权余量内3次诊断（1次400、真实规划成功、临时局真实流式正文成功），已记录评估累计97／120，不含用户自行游玩，不继续无授权追加。后端PID6148／工具session48646已加载修复，健康、代理及受影响局GET200；10份真实存档SHA-256不变，玩家可点原“恢复本轮”，未替玩家执行。保持当前相关脏分支，无提交／推送；本轮无前端或模组配置改动。详见[格式兼容修复](../design/done/deepseek-schema-recovery.md)。

2026-10-24：用户要求扩充调查、线索用途和关键决策。在feat/expand-investigation保留前轮相关未提交改动实施v3（3.0.0）：11场景／61交互定义／23类线索，增加查档、河墙、音乐室、巢窟、陷坑；旧信支持备用出口，新近烟头／鞋印只在失踪线出现并支持循迹绕坑，观察地形支持免检定，音乐以明示1SAN换取声音掩护，家族资料＋遗言或可疑饮水支持安抚，结案按实际证据／同行或营救表述。保持双时间线与随时撤离，支线不强制收齐。

新局current=v3；registry.retained冻结原v2指纹，已有局／重复创建请求继续原配置，v1仍只迁移到v2。GET不写盘，新版损坏不阻塞旧局，未知指纹与旧版篡改明确报错；无专用剧情Python分支。通用Ending.returnRoutes支持选定的河岸返回地点，公开DTO／SSE不改。原模组／素材／模板／真实存档／密钥不改。

验证：253项后端离线测试、覆盖全部11场景的完整调查、current/retained配置校验、CLI help；前端npm ci/lint/typecheck/build及四项离线适配检查通过。无真实模型调用或真人时长测试，无新UI布局而未重复浏览器QA。旧付费脚本只恢复已有v1/v2报告，避免把旧路线跑在v3上。设计与结果见[调查扩充](../design/done/darkness-investigation.md)。本地后端已重启到当前代码（PID94060），健康与Vite代理200，既有game_id读取200、无未决回合、存档字节未改。当前分支feat/expand-investigation；未commit/push。

以下为运行器重构及此前记录：

集成后已重启当前40da本地后端（原服务未开自动重载），用既有game_id只读GET验证200、新公开英文标题及存档字节不变；没有发送游戏行动。临时开发worktree已归档，当前修改位于40da的feat/module-runtime，未提交／推送。

2026-10-24：按用户要求在feat/module-runtime将网页运行器改为“结构化模组＋Agent通用工具”。新增data/runtime/index.json、v2 schema及岭下暗影v2配置，按每局moduleId/runtimeProfile解析；初始化、NPC知识／可见性／跟随、素材、地区、场景和结案不再写专用Python分支。模型提交move/observe/talk/take/inspect/interact/finish，普通观察／交谈开放，关键效果由配置校验，挑战允许在配置技能／辅助物品中选择策略并按方法限次。叙述不接收原始flags或未来剧情；结案事实由模组条件文本区分。前端英文标题来自后端，素材ID支持连字符。

原v1及完整内容包不改。明确登记v1指纹→冻结v2目标，GET在内存升级不写盘；下一次原子保存保留备份。旧计划／尝试转换，已保存出目、checkId、消息／请求与已提交效果保持；未提交回合复用原骰子，已提交只补正文，未知版本报错。独立worktree开发与验证后回到40da工作区集成，保留此前9个状态提示未提交文件，不自动stash/revert/commit/push。

验证：237项后端离线测试（含原创天文台模组的端到端／重启／HTTP-SSE、多模组隔离、策略／技能／道具与迁移断点）、只读配置检查、CLI帮助；前端npm ci/lint/typecheck/build及目录/SSE/继续调查/状态变化脚本通过。无付费调用、真实存档修改或新依赖。此轮未重复浏览器布局测试，只有副标题／公开类型数据化；此前状态提示浏览器证据仍有效。真实模型新提示尚未评估，原会话94次请求预算记录保留，不能无授权续跑。玩法长度未扩展；新模组需整理运行配置，不能只提供原文或完整战斗便自动执行。见[接入](../runtime-profiles.md)、[ADR-0005](../decisions/ADR-0005-module-driven-runtime.md)、[交付](../design/done/module-runtime.md)。

2026-10-24：feat/game-state-feedback新增“本轮变化”面板，场景左下角显示实际HP／SAN／MP／幸运增减、物品与线索变化，8秒自动关闭，悬停／聚焦保留，可手动关闭及内部滚动。GamePage按最近公开快照比较，初读、刷新、同版本完成／重连、旧版本／跨局不重放；不按模型文案推测数值，不额外持久化。新增game-changes.ts、GameStateFeedback与离线回归脚本；设计见docs/design/done/game-state-feedback.md。npm ci/lint/typecheck/build、新差异与既有SSE检查、浏览器1440×900／1280×720／390×844及自动消失／聚焦／刷新／恢复通过，无控制台错误。使用浏览器HTTP夹具，不改真实存档、不调用模型；后端未改，未重复全量测试。状态条修复已在355488e提交，此轮未提交／推送。

同轮只读排查“流程短”：6场景／35事件并非35个必经剧情点，问话／遗骸／侦查／壁画可选，已有工具可跳过准备和危险检定，最终遭遇一次检定或固定代价即可通过；原评估失踪13回合、同行含可选21回合，20–30分钟从未做真人时长验收。已向用户建议增加线索用途与关键决策，玩法扩充尚未实施，以避免改变当前运行配置指纹和已有存档兼容。

2026-10-24：在fix/game-resource-meters修复游戏侧栏固定色块不随数值更新的问题。GamePage与game.css改为固定底槽＋按当前资源填充；HP／MP使用各自上限，SAN／幸运按100，缺值／无有效上限留空、比例限制在0–100%。同步simplified-mvp展示约定。npm ci/lint/typecheck/build通过；浏览器1440×900确认初始比例，通过仅在浏览器拦截的SSE夹具验证7/14HP＝50%、32SAN＝32%、0/13MP＝0%、25幸运＝25%，1280×720与390×844无横向溢出，移除夹具刷新恢复真实数值。无控制台错误，不改后端／真实存档、不调用模型，故未重复后端测试；本次未提交／推送。此前继续调查功能已在6a087b3提交。

2026-10-24：在新分支feat/resume-investigation接通首页“继续调查”。frontend/src/state/recent-game.ts只把最近可恢复game_id记在localStorage（coc:last-active-game）；创建／直接游戏地址读取更新，最终结案只清除同一局。ContinueInvestigation在首页进入／聚焦／跨标签变更时GET校验，显示案件和人物，跳回原地址；空或404禁用，网络／损坏／版本错误保留编号并重试。终局但最终叙述未完成仍可进入既有“恢复本轮”，不自动重发、不新增Checkpointer或后端API。旧存档需先用原地址打开一次，浏览器禁用存储时原URL仍可恢复。本轮不调用模型，未commit/push；MVP已在此前b879d31提交，首页英文已在0fe2b16删除。

验证：npm ci/lint/typecheck/build和目录／SSE／新recent-game回归通过，涵盖活动／未决／终局、404／故障、身份不匹配、取消、存储禁用及旧局不清新局。真实浏览器完成新建→首页→原game_id→刷新、断网重试、跨标签失效清理、旧结案不覆盖新局，未决入口用HTTP夹具验收；1440×900／1280×720／390×844无横向溢出，两个桌面继续按钮可见。只有主动断网／404的预期网络错误。无后端代码变化，未重复后端全量测试或付费模型；复用此前224项及恢复测试。记录见docs/design/done/resume-investigation.md，README／architecture／development／用户旅程已同步。

2026-10-24：用户批准的完整可游玩 MVP 已在 feat/playable-mvp 实现。保留开始前所有目录／封面／文档未提交改动；未 stash/revert/commit/push。当前四页和结案弹窗已接真实开局、恢复与行动：kp_agent/gameplay 独立 LangGraph（理解→工具→叙述），trpg计算，FastAPI薄适配，DeepSeek结构化规划＋真实流正文。data/runtime/darkness-solo-mvp-v1.json 的35事件／六场景支持乔什立即同行或次日失踪、装备／线索、普通D100、HP/SAN和完成／撤离／失败；完整原包仍不宣称全面可执行。网页不再引用旧game-preview假回复；旧图片按用户要求保留。

每局 saves/<id>/game.json＋有效备份／校验和，出目先保存、效果一次提交、正文最后保存。单worker进程锁、同局接收锁、未决回合限制；请求幂等，断线不取消任务，刷新／重启从同请求恢复，不重掷或重复扣资源。创建URL为#/game?game=<id>，没有存档管理页。素材由本局授权接口返回，原始模板／存档／密钥不传前端。确认撤离和固定3HP通过使用确定性提示，未确认不执行。叙述上下文动态反映当前通路／乔什，提示mvp-2修复旧场景文案覆盖当前进度的问题；模型措辞仍有偏差风险。

验证：224项后端离线测试、CLI帮助与临时SQLite demo；前端npm ci/lint/typecheck/build及目录／SSE拆块适配通过。真实DeepSeek两线34回合状态与事件映射通过，加浏览器6回合和确认回归2回合；本轮累计94次模型请求（授权上限120），后续不要无授权追加付费评估。初版正文发现过通路和乔什描述不一致，已修正并做针对性真实回归，未将旧报告改写为完美结果。桌面1440×900／1280×720、窄屏390×844、检定静态恢复、断线和重启、结案关闭／重开／键盘返回通过；长历史辅助文本撑高外层页面已修复。未测Windows或真人游玩时长。详细证据见 [评估](../evaluation/playable-mvp.md)，[API](../interfaces.md)、[架构](../architecture.md)、[ADR-0004](../decisions/ADR-0004-web-game-runtime.md)。实施设计已移入docs/design/done/。下一步由用户试玩反馈决定，不扩展复杂CoC、多人或认证。

以下为此前阶段记录（其中“尚未实现”等仅描述当时状态，已完成设计现位于docs/design/done/）：

2026-10-23：用户要求记录单人简化版 MVP，并明确现有 LangGraph 若不合适应优化。新增 docs/design/active/simplified-mvp.md，作为后续 M3／M4 玩法与实现计划入口：AI Keeper 负责动态叙事、NPC、自由行动理解、受约束工具规划与结果主持；普通 D100 只分成功／失败，少量 HP／SAN，单次危险替代完整战斗，阶段触发替代计时。建议 5–6 场景、3–5 关键检定、20–30 分钟为待试玩目标，成功／撤离／失败三类结案；原模组只读另写简化配置，乔什时间线等实施前定稿。网页存储拟按 `saves/<game_id>/game.json`＋有效备份保存完整状态／对话／回合；单进程同局锁、原子写、出目／效果幂等、先提交再叙述及失败恢复保留。旧 SQLite CLI 仍为现状，LangGraph 先评审分流／注入／恢复再改，不把当前线性图定死。同步 backend-integration、architecture 和 README 入口；当前预览素材按用户要求不动。本轮仅文档，未实现运行时、调用模型或修改数据。验证：git diff --check、5 份文档的 UTF-8／代码围栏／25 处本地链接检查通过；无代码变更，未重复后端测试和前端构建；未提交／推送。

2026-10-23：按用户要求使用 coc-module-builder 与内置imagegen新生成岭下暗影封面 assets/module-cover-v1.webp（1024×1536不透明WebP），登记manifest.presentation.cover、assets索引、asset-plan完整提示词／单次生成记录及当前指纹。沿用用户既有批准风格，agent审阅通过，不宣称用户另行批准新图。发布清单改为coverAsset，封面服务核对manifest与索引kind／MIME后按模组根目录返回；data/public已删除，接口URL不变。封面只用公开引言，美术陈设不作为地图事实。 验证：208项后端单测、目录／游戏适配smoke通过；模组--complete零错误零警告（25项生成素材skip，34项索引）；浏览器确认封面GET加载1024×1536新图。前端源码未改，未重复lint/build；未调用游戏模型、未改游戏执行器或存档。

2026-10-23：按用户要求精简前端：移除模组详情年代／地点／玩法／原作人数／内容提示、单人改编预览标签、后端来源提示、DSAI5205页脚、人物数量／来源说明与准备弹窗预览说明；全站设置入口及对应面板移除，确认按钮改为“开始调查”。动画继续遵循系统偏好；后台目录字段、真实资料与游戏结束响应处理保留。前端lint/typecheck/build、目录与游戏smoke通过；未改后端逻辑，未重复后端测试。

2026-10-23：feat/catalogue-api 按用户授权实现 M1/M2：公开模组列表／详情／封面、模组调查员列表／详情／头像 GET。data/module-catalogue.json 显式允许清单映射模组ID与十位调查员；Catalogue 从 manifest 与 YAML／Markdown 构造公开投影，不静态挂载后台数据。前端 fetch＋响应校验、取消和错误重试；移除假目录、假人物与假图集，封面移到后端公开目录。人物页保留内部滚动，游戏使用真实人物资料但动作／结案仍为演示，M3/M4未实现。直接声明 PyYAML 并同步锁，未升级其版本。此前相关未提交文档均保留。契约 docs/catalogue-api.md，设计 docs/design/active/backend-integration.md，决定 ADR-0003。
验证：207项后端全量离线测试（含目录边界）、CLI help；前端 npm ci/lint/typecheck/build、目录／游戏 smoke；浏览器1440×900和390×844、头像、内部滚动、确认跳转、断线恢复通过。无模型调用／DB写入；未在Windows运行或推送。

2026-10-23：docs/user-journey-and-storage 基于 taosdev 当前代码新增 docs/user-journey.md、module-storage.md、character-storage.md，并在 README 提供入口。记录四页＋结案弹窗、模组0.2.0与运行能力区别、调查员/NPC/前端mock三类人物、版本/出处/素材索引/本局状态边界，以及前后端模组ID差异。仅文档变更，不修改数据、接口或运行时。

2026-10-23：经用户要求，将fix/darkness-module-adjudications的87db34a合并到taosdev，保留现有游戏预览和结案弹窗。模组裁定与运行时能力边界不变；本次未推送。

2026-10-23：用户将结案简化为游戏内弹窗，取消独立总结页/统计。feat/investigation-ending-dialog 实现结束标题、复用最终 Keeper 叙述、“返回首页”；公开展示 DTO 支持可选 ended，设置提供 ending-preview。关闭可回看记录/重新打开，但行动不恢复；不新增真实 HTTP、总结接口或模型调用。实现记录 docs/design/done/investigation-ending-dialog.md。验证 npm ci/lint/typecheck/build、扩展离线 smoke、桌面/窄屏/短屏弹窗、关闭/重开/返回首页通过。无后端改动，未重复后端测试；真实结束实例限制待正式接口接入。

2026-10-23：按用户要求移除游戏主界面侧栏的“存档 · 暂未开放”按钮，清理专用样式与 Lock 导入。

2026-10-23：feat/gameplay-preview 从干净 design/frontend-ui 建立，实现开场游戏 UI。调查员确认进入 #/game，沿用所选假人物；住宅背景与乔什透明立绘分层，固定内部滚动对话、自由输入、建议、人物/物品/线索/记录/设置抽屉。api/game.ts 暂为固定离线回复，正式 HTTP/规则/存档未接；设置中的检定仅固定展示。仅两张已审阅开场图进入 frontend 静态预览允许清单，不改变原模组 keeper_only，未来必须由服务端按本局授权素材。接口草案 docs/game-preview-api.md，工作记录 docs/design/done/gameplay-preview.md。验证 npm ci/lint/typecheck/build、离线适配 smoke 和桌面/窄屏核心交互通过；无后端改动，未运行真实模型或重复后端单测。待正式游戏 HTTP、状态/素材授权与网络恢复。

2026-10-23：fix/darkness-module-adjudications 按用户授权处理16项疑点，内容版本0.2.0；新增rulings.yaml及只读检查，manifest记录裁定摘要及能力。HP11、妖鬼SAN0/1D8补齐；其余歧义采用显式项目裁定，照片/原附件以限制措施结案，不称恢复原件；地图为显式场景抽象并有高差/危险/笼门/传送门禁，非精确战术地图。191后端单测、专用约定检查、标准--complete（零错误/警告）通过；正文/图像字节不改，历史配置与指纹归档。尚未实现事件执行、法术适配、单人游玩测试，runtime_compatible仍false；不将issues resolved等同运行就绪。交付见docs/design/done/darkness-adjudications.md；未提交合并推送。

2026-10-23：用户明确通过新增素材审阅，24项生成素材全部accepted并登记assets/index.yaml（加9项原材料共33项）。重复ID已通过仅将事件degenerate_origin重命名为investigate_degenerate_origin解决，线索ID及事件clue引用保持原状；内容版本0.1.1，图像字节不改，旧生产指纹/索引归档assets/visual-approval-history-v1.json，核对仅ID区分后更新当前验收指纹。标准--complete校验通过，24项均skip；规则/地图/原始来源等既有issues保留，runtime_compatible仍false。

2026-10-23：经用户要求，将 feat/coc-module-builder-skill 与 feat/darkness-visual-assets 合并到 design/frontend-ui；保留目标分支仓库清理与手动验证约定。合并仅上下文文档冲突，保留两侧记录。素材审阅状态和既有模组校验问题不因合并改变。

2026-10-23：按用户要求删除 .github/workflows/ci.yml，后端测试和前端 lint/typecheck/build 改为开发者提交前手动执行。历史初始化报告中的 CI 描述仅反映当时状态。

2026-10-23：design/frontend-ui 已快进合并到 taosdev。按当前 frontend/backend/skills 目录调整根 .gitignore、.gitattributes、.editorconfig：运行输出按目录忽略，JSONL/ZIP 样本和素材不再全局排除，保留依赖锁和评估证据。

2026-10-23：经用户要求，将 coc-module-builder 提交并合并到 design/frontend-ui；保留角色卡导入 skill 及前端已有功能。合并验证继续使用该 skill 的 34 项离线测试，真实素材试制另行进行。

2026-10-23：经用户要求，将角色卡导入 skill 提交并合并至 design/frontend-ui，保留该分支已有调查员选择页。技能仍为独立工具，不接游戏运行时。

2026-10-23：在 feat/coc-character-import-skill 新增自包含技能 skills/coc-character-card-import/，固定生成 character.yaml、background.md、可选裁切头像，无 manifest，不依赖本项目角色类、数据或对话。项目目录是维护源，已按普通文件复制到个人 Codex skills 目录，未自动提交/推送。
验证：quick_validate 对源码/安装副本通过；29 个隔离脚本场景通过；仅给技能和三张图片的独立试用完成 3 位角色，局部复核修正字符误读，最终 0 错误，原文疑点保留为警告；已有十人只读校验 0 错误。npx skills 本地发现及临时项目 --copy 安装通过，最终文件与维护源逐字节相同；后端191项通过。未修改前端/运行时/已有角色，未调用外部模型API。交付记录见 docs/design/done/coc-character-import-skill.md。
后续：GitHub 默认分支发布后，外部用户才能直接用 npx skills add FOC4869/TRPG-kp-agent 获取此技能；尚未验证远端安装。独立原图复核还发现既有 david 卡将“一双手铐”记成 quantity=2、unit=双，属于待单独修订的数据错误，本轮按约定未改旧角色。

2026-10-23：用户认可首批并要求续做，feat/darkness-visual-assets 新增18张背景及斯西亚·瑞斯、退化人、妖鬼3张基础透明立绘；共24张均落盘，尺寸/解码/哈希/真实alpha检查通过。完整调用提示词及参考路径写入asset-plan；首批3项accepted进入索引，新增21项review等待审阅；历史厅火盆、传送门矩形刻纹、生活区植物等美术偏差已留review_note。visual-preview.html支持背景/人物切换与16:9/21:9，未运行浏览器QA；visual-validation.json区分正式校验和继续阶段诊断，二者均仍报告既有degenerate_origin重复ID，不能称整包通过。未改运行时/前端，未提交推送。

2026-10-23：feat/darkness-visual-assets 按 coc-module-builder 制作默认背景、文斯考特宅开场背景、乔什基础真实透明立绘候选，保存 assets/；24 项制作计划（含共享背景及4种基础形象），style 为 draft，3项 review，其余待选风格。visual-preview.html 提供16:9/21:9独立图层预览；未接前端、未覆盖出版物附件、未写可用索引。校验被既有跨实体重复ID degenerate_origin 阻断；原始文本附件缺失，派生 source-text 明确记录来源及原哈希差异，不能宣称原附件字节保真。

2026-10-23：用户补充模组库需要竖版封面。coc-module-builder 新增 module_cover：1024×1536 不透明 WebP，同一画风，仅使用玩家引言信息，无文字/UI/边框，前端叠加标题标签；manifest.presentation.cover 引用。默认首批含封面、默认背景、开场背景、首位 NPC 基础立绘；已有合格封面复用。默认权限仍为 keeper_only，未实现公开投影。

2026-10-23：用户确认模组素材每个 NPC 和生物仅制作一张基础透明立绘；多个生物实例复用，不生成表情、受伤、服装或剧情状态变体，变化通过对话与文字表达。已同步 coc-module-builder 入口、视觉/格式规范和原创夹具，presentation.sprites 使用 base 键。

2026-10-23：在独立 worktree 的 feat/coc-module-builder-skill 实现 skills/coc-module-builder，可通过 Skills CLI 本地安装，完整携带内容格式、原创模板、视觉生产规范、制作计划与只读校验器。用户要求无需当前聊天上下文也能产出相同结构；默认前三阶段为整理、规划、首批样本，选定风格后续做。未迁移现有模组、未生成真实图片、未接运行时/HTTP/前端，未推送或发布。验证结果见 docs/design/done/coc-module-builder.md。

2026-10-23 后续：按用户确认的概念图实现调查员选择，仍在 design/frontend-ui；用户明确要求先用假数据和假资源，后续从 API 获得正式数据。
页面为 #/investigators?module=<id>，桌面 2×5 照片卡片，右侧概览/属性技能/背景/物品四标签。首次无选择，确认禁用；选中后可打开案件/人物确认摘要，不创建游戏或存档。
后续按用户反馈稳定右侧档案高度：四标签内容内部滚动，头像/标签/确认按钮位置固定，切换标签不再拉高整页。已检查桌面与窄屏、键盘滚动。
types/investigators.ts 定义公开展示类型，api/investigators.ts 提供 listInvestigators/getInvestigator（moduleId + AbortSignal）；当前读取独立 mock，未读取/复制 backend/data/characters 的 YAML/头像/背景。假头像图集由内置 imagegen 生成，素材提示词归档 docs/design/image-assets.md。
接入契约见 docs/investigator-api.md。下一步为游戏界面；正式 HTTP、授权摘要与模板实例/存档生命周期另行实现。
验证：npm ci/lint/typecheck/build、适配层 smoke、桌面/宽屏/短屏/窄屏浏览器检查、四标签键盘导航、选择确认与无效上下文均通过；无后端改动，未重复后端测试。交付记录见 docs/design/done/investigator-selection.md。

以下为服务端资产合并历史：

2026-10-23：将 feat/preset-investigator-data 合并回 design/frontend-ui；保留目标分支现有模组库/详情页及《岭下暗影》内容包，新增十位预设调查员。角色目录仍未接入页面和游戏运行链路。

2026-10-22：在独立分支 feat/preset-investigator-data 按用户确认的格式新增十位预设调查员，位于 backend/data/characters/<id>/{character.yaml,background.md,assets/portrait.png}。无角色包层、无 manifest、无完整角色卡截图；结构不受现有 Character 实现约束。没有移动旧 Excel 或接入运行时/HTTP/前端。
角色数值、背景、原卡留白、装备和裁切头像已转录；作家伤害、记者历史/图书馆括号值等疑点保留在 source_issues，不自行裁定。魔术师钥匙特例是数据描述，尚无执行实现。字段约定见 backend/data/characters/README.md；交付记录见 docs/design/done/preset-investigators.md。
验证：十份 YAML 的唯一键/ID、属性技能范围、资源、攻击技能引用、嵌套装备、文件/锚点引用及十张 PNG 解码检查通过；头像合览人工检查通过；后端 191 项离线测试通过。无模型调用和依赖变更；本任务未修改前端，未重跑前端检查。原有首页及文档未提交改动保留，仅在 README/architecture/development/active-context 增补本次数据说明。
后续接入需单独实现角色目录加载、规则默认值与疑点裁定、角色实例快照及授权投影，不把静态数据完成等同于游戏功能完成。

2026-10-23：将 feat/darkness-module-package 合并回 design/frontend-ui；保留现有首页/模组库，新增服务端模组内容包。两者尚未接成游戏运行链路。

2026-10-22：在独立工作树 darkness-module、分支 feat/darkness-module-package 新增《岭下暗影》内容包。基于创建时 HEAD 20494e4，未带入原工作区 design/frontend-ui 的未提交首页改动。

交付：backend/data/modules/darkness-beneath-the-hill/，完整正文38锚点、10个YAML、45个事件提取、7张原图与2份正文展示材料索引；assets/统一存储，无固定媒体分类子目录。素材原始字节保留，默认keeper_only。

范围：声明式内容草案，不改变现有campaign.json、KeeperService、CLI、HTTP、前端或SQLite；未实现运行时加载/检索/授权。原文规则争议、地图逐边核准与外部规则依赖见包内issues.yaml。

验证：完整正文往返、YAML重复键/出处/实体引用、素材哈希、默认权限检查通过；后端191项离线单测通过。未改前端，未运行前端检查；未调用真实模型。设计与验证见 docs/design/done/darkness-module-package.md。

下一步：先核准地图连接、规则版本、蛇人HP与其他issues，再单独设计内容schema/loader到执行器的适配；不要将此包直接交给现有--campaign加载器。

以下为前端与工程交付记录：

2026-10-22 后续：用户要求先提交首页再实现模组库；首页已提交 ace06d5。
当前新增分页模组库/详情（#/modules），桌面每页 3 张卡片、左右翻页、首尾禁用、末页不补空卡。首页开始调查已跳转新页面；选择调查员仅弹出尚未开放提示。
主模组确定为《岭下暗影》，只使用用户提供的玩家引言，封面表现地窖/提灯/未知通道，不传守秘人信息。api/modules.ts 暂时读取本地 typed fixture（1 个主模组 + 6 条待收录记录），不请求不存在的后端目录接口。
新封面为内置 imagegen 原创生成；底层与后端未改。下一步为调查员选择界面；接游戏 API 前仍需确认存储与服务生命周期。
验证：npm ci/lint/typecheck/build、分页适配 smoke、桌面/宽屏/短屏/窄屏浏览器检查、选择/翻页/焦点/返回/刷新均通过。交付记录见 docs/design/done/module-library.md；完整素材提示词归档 docs/design/image-assets.md。

以下为首页交付记录：

2026-10-22：chore/standardize-project-structure 已快进合并到 taosdev；当前 design/frontend-ui 分支实现桌面首页。
用户确认首页 → 模组库/详情 → 选择调查员 → 游戏（Galgame 对话）→ 结案的五页旅程。本轮仅做首页，存档/继续调查暂不实现并灰显。
首页采用原创生成的雨夜旧宅背景；标题、导航与按钮均为 HTML/CSS，兼顾电脑宽屏与短窗口。开始调查打开公开模组预览，设置含减少动态效果及按需健康检查。尚无游戏 HTTP、角色选择或完整模组页面。
前端依赖未增加；素材及最终提示词保存在 frontend/public/images/README.md。后端与原 CLI 存档机制未改。
验证：npm ci/lint/typecheck/build 通过；浏览器已检查桌面/宽屏/短屏/窄屏、弹窗和连接失败重试。首页记录见 docs/design/done/homepage.md。
下一步：按既定旅程设计模组库/详情；接游戏 HTTP 前仍需确认 KeeperService/SQLite 生命周期与请求隔离。

以下为初始化历史：

2026-10-21：用户确认将项目初始化为 frontend（Vite React TypeScript）与 backend（FastAPI + 现有 LangGraph），在英文分支 chore/standardize-project-structure 实施。

源码从 7aa25aa 的 versions/ai-kp-v1 整体迁至 backend，根目录底层测试合并；底层与 Agent 均只有一份当前实现。前端由 Vite 官方命令生成。
HTTP 只提供 GET /api/health；React 页面用于检查连接。游戏接口、聊天页面、多人会话和数据库替换未实现。
依赖与启动以 README/development 为准。个人秘密、存档和虚拟环境不迁移。

下一步：在游戏 HTTP 接口实现前确认 KeeperService/SQLite 生命周期与请求隔离，更新接口契约；前端产品界面按实际需求另行设计。
目录迁移决策见 ADR-0001，路径和规则测试冲突见 history/structure-migration.md。

验证：191 项后端离线测试通过；CLI demo/重试、健康接口与 Vite 代理通过；前端 lint/typecheck/build 通过。未调用付费 API，未在本地运行 Windows 或远端 CI。完整初始化记录见 docs/design/done/project-bootstrap.md。
