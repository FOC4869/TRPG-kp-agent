# COC 单场景 AI KP：Agent＋RAG 开发版

本目录是新增版本，仓库根目录的原代码保留不变。请先进入 `versions/ai-kp-v1/` 再安装依赖和运行。

目前按小组已经决定的范围做：**一张固定角色卡、一个玩家、一个场景，AI 直接当 KP**。
角色和骰子沿用队友的 `trpg/`；新增部分主要在 `kp_agent/`。

## 现在能做什么

- 用 LangGraph 串联行动理解、追问、规则检索、场景检查、掷骰、保存、叙述。
- 读取仓库里的理查德角色卡；一次启动后，从 SQLite 读取最新状态。
- 自建“旧书房”短场景：观察、搜索、与管家交谈、一次理智事件、离开结束。
- 检索 13 项首版规则，返回出处、PDF 页码和书内页码；已有的规则检索接口保持兼容。
- 真实随机骰、成功等级、难度达标、SAN 变化和日累计损失计算。
- 保存角色、线索、事件、消息和骰子。重复消息不重复执行；回复失败可恢复。
- 未揭示的线索由场景代码保管，不传给模型；最后叙事只接收允许公开的结果。
- 开场和普通行动后提示可以尝试的下一步，只用公开信息，并过滤已完成的调查和交谈。

**当前没有 React 页面或 FastAPI 路由。**先用命令行和 Python 入口接通，方便网页同学继续做。

## 先跑离线演示

当前机器的 `.venv` 已经装好依赖，进入本目录后直接运行：

```bash
.venv/bin/python -m kp_agent --mode demo
```

macOS 也可以双击 `run_demo.command`，它会打开命令行演示。

如果换一台电脑，使用 Python 3.12 或更新的兼容版本，新建环境并安装：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-agent.txt
.venv/bin/python -m kp_agent --mode demo
```

### Windows 启动

建议组员统一使用 Python 3.12。Windows 的虚拟环境需要在自己的电脑重新创建，不能直接复制 Mac 的 `.venv`。
在项目目录打开 PowerShell，第一次运行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-agent.txt
.\.venv\Scripts\python.exe -m kp_agent --mode demo
```

装好后，可以双击 `run_demo.bat`。真实模型模式先按下文填写 `.env`，再双击 `run_deepseek.bat`。
Mac 继续使用同名的 `.command` 文件。Windows 编辑 `.env` 时请选择 UTF-8、不带 BOM。
Windows 启动文件会切换到项目目录并启用 UTF-8；
核心 Python 代码、场景和角色卡共用一份。Windows 还需要在实际机器上确认运行，不能把 Mac 的检测结果当成 Windows 实测。

`demo` 是**离线关键词判断模式，不是大模型**，只用于检查流程；开头会明确显示。
骰子仍是真实随机数，因此搜桌子可能失败，不能保证每次得到完整结局。

可以依次输入：

```text
看看房间
我想检查一下
书桌
问问管家
检查壁炉
临时疯狂怎么判定
离开
```

命令：`/status` 查看状态，`/history` 查看聊天，`/retry` 恢复失败消息，`/review` 在结束后复盘，
`/restart` 恢复初始角色并重开，`/quit` 保存退出。
每个行动自动保存，不用手工“保存游戏”；下一次启动继续原存档。
有未完成消息时先 `/retry`，否则不能继续新行动。
如果上一局已经输入“离开”并结束，再打开程序会明确显示“已读取存档，本局已结束”，
不会重播新开场。此时用 `/restart` 才会恢复角色初态并开始新一局。
已结束或暂停时，新的行动不会调用模型、检索规则或改变游戏进度。
本场景结束后，可以直接问“什么信息没有找到”或输入 `/review`。
复盘会说明本局已找到和遗漏的线索，但不会改变角色、补发奖励或重新打开已结束的游戏。

书桌的首次侦查失败后，可以选择“花十分钟仔细检查书桌”。这会消耗故事里的十分钟，
采用本场景写好的另一种调查方式，不重掷骰；重复执行不会重复耗时或再次发线索。
这是这间书房的设计，不代表所有 COC 检定都可以花时间自动成功。

每次结果后的下一步提示是建议，**可以继续自由输入，不必照着选**。
提示不会透露未发现线索，也不会重复推荐已经完成的调查或交谈。
AI 正在追问、需要真人接管、游戏暂停或结束时，不另外显示普通行动建议。

## 接入真正的大模型

目前使用 **DeepSeek 官方 API 的 Flash 模型**。2026-10-21 已完成真实对话回归，
包括预设失败路径、真实随机骰、完整和未完成结局。检测记录见 `output/qa/2026-10-21_repair_check/`。

1. 把项目里的 `.env.example` 复制成同一文件夹下的 `.env`。
2. 在自己的 `.env` 中填写 `DEEPSEEK_API_KEY`，不要把 key 发到聊天或群里。
3. macOS 双击 `run_deepseek.command`，或者在项目目录运行：

```bash
.venv/bin/python -m kp_agent --mode deepseek --db saves/deepseek.sqlite3
```

DeepSeek 模式使用独立的 `saves/deepseek.sqlite3`，与命令行离线演示的默认存档分开。
下次打开继续这份存档；只有输入 `/restart` 才重开。更新代码后，旧终端先 `/quit`，再重新启动。

程序自动读取项目根目录 `.env`，不会覆盖终端已经设置的同名环境变量。
建议将自己电脑上的 `.env` 权限设为 `0600`；修改配置后退出并重新启动才会生效。
示例中 `KP_MODEL_MODE=demo` 保留离线默认值；`run_deepseek.command` 和 `--mode deepseek`
明确选择 DeepSeek。`run_demo.command` 始终运行离线演示。

模型名填写 `deepseek-flash`。按 DeepSeek 当前官方说明，这个名字对应 V4.1-Flash-1017；
原 V4-Flash 已升级，旧名字也会转到新版，不能用它固定旧模型。
默认关闭思考（`DEEPSEEK_REASONING_EFFORT=none`），先让聊天响应快一些。
普通一轮通常有“理解行动”和“叙述结果”两次模型请求；追问通常只需一次。
DeepSeek 不在后台自动重试，失败时使用 `/retry` 恢复原消息。
先保留关键词 RAG，不用同时配置向量 API。

接入沿用 OpenAI Python SDK，通过 DeepSeek 的 **Responses API＋JSON Schema** 返回结构化数据，
本地再检查格式、目标和引用。模型仍不负责实际掷骰或直接改角色数据。
调用用量记录在 `saves/model_calls.jsonl`，仅含时间、模型、阶段和 token 用量，
不记录密钥、原始提示词或完整思考内容。用量来自 API 返回；未返回则为 `null`，不是精确账单。
新版日志也带游戏、消息和行动编号，以及受控错误类型。只有格式、目标和引用都通过本地检查，
才记为 `accepted`；旧日志中的 `parsed` 只说明当时解析成功。

原有 `--mode openai` 也保留；只使用 DeepSeek 时不用填写 `OPENAI_*`。
任何在线模式缺少配置都明确报错，不会自动换成其他服务或离线模式。
详细说明在 [docs/model_setup.md](docs/model_setup.md)。

## RAG 的运行方式

默认关键词检索，不需要联网。小范围资料在 `data/agent_rules.md`，由已提供的规则书人工核对。
它是带出处的摘要，不是完整规则书，也不包含模组秘密。未知问题可以没有检索结果。

可选向量检索要显式设置 `KP_RETRIEVAL_MODE=openai_embeddings`、
`OPENAI_EMBEDDING_MODEL` 和 `OPENAI_API_KEY`。首次建库会调用 embeddings API，可能产生费用；
之后缓存到 `saves/rules_index.json`。换资料或嵌入模型会重建，普通查询不重复计算所有资料向量。
目前向量调用只做过模拟 API 测试，尚未用真实服务验证质量。

## 代码怎么分

| 文件 | 做什么 |
|---|---|
| `kp_agent/graph.py` | `KeeperService` 入口和 LangGraph 流程 |
| `kp_agent/models.py` | 离线规划、真正模型的行动规划与公开叙事 |
| `kp_agent/schemas.py` | 模型只允许输出的行动字段 |
| `kp_agent/retrieval.py`、`trpg/rules_store.py` | 规则检索、来源和缓存 |
| `kp_agent/embeddings.py` | 可选向量服务配置 |
| `kp_agent/scene.py`、`data/scenes/study.json` | 固定场景、检定条件、公开与隐藏信息 |
| `kp_agent/guidance.py` | 按公开状态和已完成行动整理下一步建议 |
| `kp_agent/tools.py` | 调用队友引擎、难度比较、幂等骰子、理智结算 |
| `kp_agent/storage.py` | SQLite 存档、消息、骰子、行动原子保存 |
| `trpg/character.py`、`check.py`、`dice.py` | 队友现有的角色与骰子实现 |

存档真实数值以 `Storage` 为准，模型不能从聊天记忆里修改数值。
LangGraph 每条消息运行一次；跨进程恢复用数据库中保存的计划、骰子和行动结果，
没有另外宣称实现 LangGraph 的持久化 checkpointer。

## 给网页同学的最小调用例子

```python
from kp_agent.graph import KeeperService

keeper = KeeperService()
game = keeper.start()  # 已有存档时返回存档，不会覆盖
reply = keeper.handle_message(
    message_id="每条消息一个固定编号",
    text="我检查书桌",
    game_id=game["game_id"],
)
# 返回 reply、rolls、changes、character、new_clues、evidence、progress 等。
# suggested_actions 是可选建议列表，guidance 是适合直接显示的提示文字。
# 超时后重试同一消息时，编号和 text 都保持不变。
keeper.close()
```

HTTP 包装层必须把网页传来的游戏编号传进来，拒绝重开前的旧请求。
在异步 Web 路由中，不要直接在事件循环里运行同步模型请求；交给适当的工作线程。
`start()`、`restart()`、`get_game()` 和消息结果均可带 `suggested_actions`、`guidance`。
网页显示 `guidance`，或者把 `suggested_actions` 做成可选按钮，二者择一即可，保留自由输入框。
完整接法见 [docs/interfaces.md](docs/interfaces.md)。

## 检查代码

```bash
.venv/bin/python -m unittest discover -s tests -t . -v
```

使用 `-t .` 是因为队友原来的测试有相对导入。
测试使用临时数据库和明确标记的预设随机数，不调用真实付费 API。
运行测试时建议显式固定关键词检索，避免本机曾设置过向量服务：

```bash
KP_RETRIEVAL_MODE=keyword .venv/bin/python -m unittest discover -s tests -t . -v
```

`scripts/live_regression.py` 是另外的真实 DeepSeek 检查，会产生 API 用量，需要手动运行。
它要求全新或空的输出目录，使用独立数据库、规则索引和日志，不使用玩家存档。
预设骰子 69、95、1 仅用于重现失败路径；日常启动器仍使用真实随机骰。

```bash
.venv/bin/python scripts/live_regression.py --output-dir output/qa/自己新建的测试目录
```

## 第一版的限制

- 正式模组未确定，暂用自编场景；未解析或剧透《幽暗之门》。
- 只允许场景已写好的行动与结果，不是任意行动都能自动主持。
- 首版不做完整战斗、追逐、成长、法术和孤注一掷；请求超出范围会明确提示。
- 原角色引擎存在尚未全面核对的规则边界。首版调用层只覆盖已使用的检定与理智逻辑，
  不把旧代码注释中的“事务更新”当作数据库事务；原子保存由新增 SQLite 层完成。
- 已实测 DeepSeek 的当前短场景；其他模型、网络条件和更多口语表达仍需另外验证。
- 小组仓库为 `FOC4869/TRPG-kp-agent`；各自的密钥、虚拟环境和玩家存档不放入仓库。

最初使用 GitHub codeload 下载了精确源码快照，原始来源 commit 记录在 `SOURCE_SNAPSHOT.txt`。
后续开发改动以 Git 提交记录为准。

参考实现资料：
[LangGraph Quickstart](https://docs.langchain.com/oss/python/langgraph/quickstart)、
[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)、
[DeepSeek Responses API](https://api-docs.deepseek.com/zh-cn/guides/responses_api/)、
[DeepSeek 思考模式](https://api-docs.deepseek.com/zh-cn/guides/thinking_mode/)。
