# COC AI KP v2：三个地点的 Agent＋RAG 开发版

这是 Agent＋RAG 最新实现（v2），按要求更新在原来已发布的 `versions/ai-kp-v1/` 目录，旧链接继续可用。
仓库根目录原始代码保留。较早的单书房版本可在 Git 历史提交 `d845b73` 中查看。

这一版仍然是**一名玩家、一张固定角色卡、一个 AI KP**，把原来的书房故事扩展为
**旧书房 → 车站 → 档案室**三个地点。玩家可以调查、交谈、带着已找到的线索和物品前进，
也可以沿已开放的出口回访，最后结束整段故事。

当前配置为 **3 个地点、8 条线索、4 种物品、17 个规则主题**。
v2 当前 98 项离线测试全部通过（较早 60 项＋本次补充 38 项），此前也做了真实 DeepSeek 的自由表达与少量整轮检查。
这些检查不是随机跑团全程通关证明；结果和仍然存在的问题见下文及
[本次检测记录](docs/泛化测试结果_2026-10-21.md)。
试玩反馈、原因、修改及前后证据统一保存在 [问题发现与修复记录](docs/问题发现与修复记录.md)。

## 这一部分由谁做

你负责的是 Agent＋RAG：理解玩家的话、追问、查规则、按当前地点选择行动、调用现有工具、
根据实际结果扮演 NPC 和叙述。正常游戏不需要真人逐条审批，异常情况可以停止自动处理并请真人检查。

React 页面、FastAPI 路由、角色与骰子引擎、最终数据库方案由另外两位开发同学负责。
目录里保留现有 Python 工具和 SQLite 适配，方便 Agent 独立接起来；不是要求你再写一套底层。
后续把同学提供的接口接到这些调用位置即可，角色数值和剧情进度始终以同一份保存结果为准。

## v2 写了哪些内容

- LangGraph 串起行动理解、追问、规则检索、场景检查、工具调用、保存和公开叙述。
- 默认从 `data/campaign.json` 读取完整故事，按当前地点提供可观察对象、NPC 和出口。
- 保存各地点调查进度、已发现线索、已得到物品、已访问地点；回访保留原进度。
- 支持调查、交谈、移动、使用已有物品和结束故事。具体条件与结果由故事文件规定。
- 沿用固定角色卡和已有角色／骰子功能，Agent 不编造骰子结果，也不直接修改资源值。
- 现有适配工具可处理 SAN、伤害、HP／MP 恢复及 MP 消耗。本故事没有法术，主线不消耗 MP。
- 可选站台行动需要 DEX 检定，失败按该事件扣 `1D3` HP，事件只发生一次。
  开局绷带恢复 2 HP 是本故事的简化约定，不等同于 COC 的完整急救规则。
- 普通失败后的书桌细查是书房预设的补救方式，不是无限重掷骰，也不是通用孤注一骰。
- 同一消息重发使用已保存的计划、骰子和结果；回复中断后可继续恢复。
- 只有整段故事结束后才提供复盘。换地点不会开放未发现的线索和后续真相。

## 怎样开始

进入 `versions/ai-kp-v1/` 再安装依赖和运行。建议组员使用 Python 3.12；依赖沿用 v1。
各自在自己的电脑建立 `.venv`，不要复制其他电脑的虚拟环境或玩家存档。

macOS / Linux：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-agent.txt
.venv/bin/python -m kp_agent --mode demo
```

Windows PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-agent.txt
.\.venv\Scripts\python.exe -m kp_agent --mode demo
```

已有启动文件：macOS 用 `run_demo.command` / `run_deepseek.command`，Windows 用对应 `.bat`。
Windows 环境需要在实际机器上确认，静态查看启动文件不代表已在 Windows 跑过。

`demo` 是**离线关键词判断，不是大模型**。它用于开发时查看行动流程；日常掷骰仍随机，
不保证每次检定成功。真正模型也只能选择当前场景允许的行动。

可以先观察房间、询问管家、调查书桌，再按当前公开的出口和线索继续。
三个地点的名字不是要求按固定台词输入；下一步提示仅供参考，保留自由输入。
想结束整段故事时明确说“结束调查”等，不要把每一次离开房间都理解为游戏结束。

## 命令行能看什么

| 命令 | 作用 |
|---|---|
| `/status` | 当前角色与公开进度 |
| `/inventory` | 已得到物品与数量 |
| `/clues` | 已发现线索 |
| `/map` | 当前地点、已访问地点和当前公开出口 |
| `/rolls` | 已提交行动中的公开骰子记录 |
| `/history` | 聊天记录 |
| `/retry` | 恢复未完成的原消息 |
| `/review` | 整局结束后复盘；中途不显示遗漏的秘密 |
| `/restart` | 明确重开，恢复固定角色与故事初始状态 |
| `/quit` | 保存退出 |

每个行动自动保存。再次启动先读本目录的旧存档，不会重播新开场或自动覆盖进度。
有未完成消息时先恢复原消息。已结束或暂停时，普通输入不再推进故事。

默认完整故事无需参数。开发时可以另选配置：

```bash
.venv/bin/python -m kp_agent --mode demo --campaign data/campaign.json
.venv/bin/python -m kp_agent --mode demo --scene data/scenes/study_legacy.json --db saves/study-debug.sqlite3
```

`--campaign` 与 `--scene` 不能同时使用。显式 `--scene` 保留旧单场景调试方式。
v1 书房存档不能直接当作 v2 故事存档；要用本版本独立存档，或明确重开。

## 大模型怎样配置

把本版本 `.env.example` 复制为同目录 `.env`，在自己的电脑填好 `DEEPSEEK_API_KEY`。
当前适配器使用 `deepseek-flash`，其余选项见示例及 `docs/model_setup.md`。
然后使用 DeepSeek 启动文件，或运行：

```bash
.venv/bin/python -m kp_agent --mode deepseek --db saves/deepseek.sqlite3
```

程序只读取项目根目录 `.env`，不会覆盖终端中已设置的同名变量。改配置后重新启动。
密钥、`.env`、`.venv` 和个人存档不要提交 GitHub。只使用 DeepSeek 时不用填写 OpenAI 账号。

模型负责规划和叙述，工具负责执行。适配器使用 Responses API 和 JSON Schema；
本地继续校验行动、当前目标和引用。显式选择在线模式但配置不全时会报错，不自动换模型。

用量文件为 `saves/model_calls.jsonl`，记录模型、阶段、耗时、token 和游戏／消息编号；
不记录密钥、完整提示词或思考正文。它是 API 返回的用量记录，不是精确账单。
本次已实际调用 DeepSeek；仍保留不自动重试的限制，真实结果见本次检测记录。

## RAG 怎样用于三个地点

三个地点**共用同一份规则知识库**：`data/agent_rules.md`，共 17 个已核对主题。
默认离线关键词检索，包含常见中文动作别名。结果带原文摘要、来源、版本、PDF 页码和书内页码。
没有依据时允许返回空列表，分数只用于排序，不能当作正确率。

玩家直接问规则时按问题检索；实际行动需要检定时，先从场景中确定合法技能，
再检索该技能与通用检定规则。发生理智事件时再查理智相关依据。
RAG 提供依据，是否获得物品、能否进入下一地点等由场景条件决定。
成功等级的数值算例由只读工具 `success_example` 调用既有检定引擎生成，带本次规则引用直接显示，
不再交给大模型重写算式。这类问答通常只调用一次 `plan`，不调用 `narrate`；
算例是明确标注的假想出目，不是真掷骰，不扣资源。其他叙述仍由模型生成。

故事内容不放进规则库：`data/campaign.json` 及各地点的隐藏信息由场景代码读取，
模型只得到当前已允许公开的目标和结果。不要把整个 `data/` 目录统一导入 RAG，
也不要把后续剧情、隐藏线索或完整复盘塞进模型的日常上下文。
新增未收录的技能时，要先补充经核对的规则来源；通用检定命中不等于该技能细则已经覆盖。

可选向量模式需显式设置 `KP_RETRIEVAL_MODE=openai_embeddings`、`OPENAI_EMBEDDING_MODEL`
和 `OPENAI_API_KEY`。首次索引未缓存资料会调用 embeddings API；后续只为查询生成新向量。
缓存通常在数据库同目录的 `rules_index.json`，资料、模型、端点或维度变化会触发相应重建。
本次未验证真实向量服务，也未为小组选定向量模型。先保留关键词模式即可继续开发。

## 组员主要看哪些文件

| 文件 | 作用 |
|---|---|
| `kp_agent/graph.py` | `KeeperService` 入口和 LangGraph 行动流程 |
| `kp_agent/models.py`、`schemas.py` | 行动理解、追问、公开叙述及允许的输出字段 |
| `kp_agent/campaign.py`、`data/campaign.json` | 三地点故事、条件、移动、物品与结局 |
| `kp_agent/scene.py`、`data/scenes/study_legacy.json` | 兼容旧书房调试 |
| `kp_agent/retrieval.py`、`embeddings.py` | 规则检索与可选向量服务 |
| `trpg/rules_store.py`、`data/agent_rules.md` | 规则切块、缓存、来源与已核对语料 |
| `kp_agent/guidance.py` | 根据当前公开信息给出下一步建议 |
| `kp_agent/tools.py` | 接现有角色／骰子函数，校验请求并整理执行结果 |
| `kp_agent/storage.py` | 现有 SQLite 适配，保存整份故事状态和行动记录 |
| `docs/interfaces.md` | 给网页与底层同学的调用说明 |

## 给网页同学的入口

```python
from kp_agent.graph import KeeperService

keeper = KeeperService()
try:
    game = keeper.start()
    reply = keeper.handle_message(
        message_id="同一条消息重试时保持编号不变",
        text="我检查书桌",
        game_id=game["game_id"],
    )
    # reply、rolls、changes、character、new_clues、evidence、progress
    # 另有 scene_transition、new_items，以及可选建议 guidance。
finally:
    keeper.close()
```

当前提供 Python 方法，没有实现 React 或 FastAPI。HTTP 地址仍由网页同学确定。
网页显示后端返回的当前场景和物品，不直接读取带隐藏内容的故事 JSON。
公开的消息、角色、线索、物品和骰子查询方法见 `docs/interfaces.md`。

## 本次检查结果与范围

| 检查 | 结果与限制 |
|---|---|
| v2 当前离线测试 | 98 项全部通过，0.274 秒；包含原 60 项与新增 38 项 |
| 本次提示与行动安全修复 | 满血建议、实际库存、已完成目标、结局面板、否定／假设与规则跟进；全套离线复查，本次无付费 API |
| 首轮自由表达规划 | 同一组 23 例，关键词 demo 14/23；真实 DeepSeek 原始规划 21/23，应用侧 21/23 |
| 修复后定向检查 | 只重查 g06、g11、g24、g25 四例，原始模型 3/4，应用侧 4/4 |
| 真实服务整轮 | 2 个 `KeeperService` 回合、4 次 API 调用，8 项结构检查通过；人工另发现一次数学说明错误 |
| 数值解释修复后 | 1 次真实 API 调用、6 项检查通过；`plan` 一次、`narrate` 零次，数值解释由程序直出 |

首轮问题包括：g06 把“怎么结束”当成规则问答；g11 把“用钥匙开站台”擅自改成开柜子。
修复后，g11 的模型原始规划仍然选错，由程序保护改成追问。
因此不能写成“模型四例全对”，也不能把定向四例当作已完整复跑首轮 23 例。
原始模型结果与应用侧结果分开保留。

整轮检查覆盖了移动、携物、重复消息／续档和合法规则引用；但人工发现规则讲解曾写出
“30≤27”这样的数学错误。已把成功等级算例改为既有引擎计算并直接显示，避免模型改写数值。
结构检查通过不等于自然语言中的每项事实都正确。

此前归档的模型检查合计 **33 次 API 请求**：探测 1＋首轮规划 23＋定向规划 4＋整轮 4＋数值修复检查 1，
没有自动重试。token 与用量明细见 [本次检测记录](docs/泛化测试结果_2026-10-21.md)。
自由表达检查使用人工构造的已知进度，只检查规划，不是随机完整跑团；两回合整轮也不等于全剧情验证。
本次修复只做离线和假响应验证，尚未重跑真实 DeepSeek；用户自行试玩的调用不计入上述 33 次。
离线关键词版现有 25 条自由表达通过 16 条，原先相同 23 条仍为 14/23，没有评分回退；
其余 9 条仍不能准确理解，不把单元测试全过写成所有自由表达都正确。

复现时使用新的输出目录。默认离线命令不会产生模型费用：

```bash
.venv/bin/python -m unittest discover -s tests -t . -q
.venv/bin/python scripts/generalization_eval.py --mode demo --output output/qa/generalization_demo_new
```

脚本现在含 25 例，其中 g24、g25 是发现问题后补充的错误物品用法；默认上限为 25 次规划。
以下定向 DeepSeek 命令**会产生 API 用量**，每例只规划一次，最多 4 次，不自动重试：

```bash
.venv/bin/python scripts/generalization_eval.py --mode deepseek --case-ids g06,g11,g24,g25 --max-calls 4 --output output/qa/generalization_targeted_new
```

当前仍只处理故事已写好的行动，不是任意模组、任意行动都能主持。
完整战斗、追逐、法术、成长、疯狂发作、通用休息换日和通用孤注一骰不在本版范围。
真人编辑、撤销、导出、多人游戏及实时网页通信也尚未实现。
本版只使用原创演示剧情，没有导入外部模组。

代码最初来源见 `SOURCE_SNAPSHOT.txt`。本次将最新 Agent＋RAG 覆盖到既有 `versions/ai-kp-v1/` 目录；
仓库根目录、`trpg/` 和 `storage.py` 底层保持原样，旧发布版保留在 Git 历史。

## 小组共用 API

组员使用组长私下提供的 DeepSeek Key，填入各自本机 `.env`。代码包保留空模板，存档各自独立。步骤与可发群里的说明见 [组员共用 API](docs/组员共用API.md)。
