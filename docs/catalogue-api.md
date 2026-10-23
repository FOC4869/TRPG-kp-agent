# 公开模组与调查员目录 HTTP

2026-10-23，已实现 M1/M2。健康接口仍为 `GET /api/health`。这些接口无模型、数据库、写入或游戏实例创建；`preview` 仅表示可进入界面预览。

| GET | 返回 |
|---|---|
| `/api/modules?page=1&page_size=3` | `{items,page,pageSize,total}` |
| `/api/modules/{module_id}` | 单条 PublicModule |
| `/api/modules/{module_id}/cover` | `image/webp` |
| `/api/modules/{module_id}/investigators` | `{module:{id,title},items:[InvestigatorSummary]}` |
| `/api/modules/{module_id}/investigators/{investigator_id}` | InvestigatorDetail |
| `/api/modules/{module_id}/investigators/{investigator_id}/portrait` | `image/png` |

分页参数：page≥1，page_size 为1—30，默认3；超过末页回末页，空目录 page=1、items=[]。未知／未发布 ID 为404，非法查询参数422，缺文件／坏配置／不安全路径503，统一错误不包含服务器路径或源文档。前端取消旧请求，失败显示重试，不返回假数据。

`backend/data/module-catalogue.json` 是发布允许清单：显式映射公开 ID、内容目录与 manifest ID，保存已批准公开引言、年代地点、卷宗号、玩法、内容提示、封面素材 ID（coverAsset）与 investigatorIds。标题取允许的 manifest，守秘人正文不读入 DTO。目前一个模组、十位人物；新增内容需要登记，发现新目录不会自动发布。

模组 DTO：id、caseNumber、title、englishTitle、status、cover、introduction、era、location、playStyle、originalPlayers、contentNote。资源 URL 为同源 `/api/...`，不公开本地文件路径。封面由内置 imagegen 按既有风格生成，存于模组 `assets/module-cover-v1.webp`，由 manifest.presentation.cover 引用；发布清单 coverAsset 必须与该引用一致，接口校验索引 kind 与媒体类型后仅返回此文件，不对整个模组 assets 开放静态服务。

人物 DTO 与客户端类型见 [调查员契约](investigator-api.md)。后端只读取已登记人物的 character.yaml、其声明的背景和头像，显式构造展示字段；不返回 source、source_issues、attacks、customization 或原模板。路径均经过根目录、父路径与符号链接边界检查，YAML 使用 safe_load。背景纯文本由 React 文本节点显示。

只读服务在 `backend/app/services/catalogue.py`，HTTP 错误映射在 `app/api/modules.py`。数据路径锚定源码位置，与进程 cwd 无关；导入 app 不初始化 Agent、不读存档、不创建文件。具体 JSON 类型可在本地 `/docs` 查看。

本地启动仍使用 README 的8000／5173两进程；Vite开发代理转发 `/api`。生产需要同源 API 反向代理；vite preview 不保证开发代理行为。

离线验证：backend 执行规定 unittest；frontend 执行 `npm ci`、lint/typecheck/build，再运行 `node scripts/check-catalogue.mjs` 和 `node scripts/check-game-preview.mjs`。脚本需要先 `uv sync --locked`，以 backend/.venv 读取真实公开投影，在测试端模拟 HTTP；产品没有该降级逻辑。Windows 可通过 `PYTHON` 指定准备好的后端解释器。

2026-10-24：PublicModule增加可空runtimeProfile，本作绑定darkness-solo-mvp。preview是兼容既有目录的发布状态，创建真实游戏另要求绑定受支持配置；不能仅凭preview宣称模组可执行。游戏接口见[interfaces](interfaces.md)。
