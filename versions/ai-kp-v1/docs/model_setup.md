# 模型怎么接

这个版本可以用离线演示、DeepSeek 官方 API，也保留 OpenAI API 的接法。

## 先用离线演示跑通

`KP_MODEL_MODE=demo` 使用 `DemoPlanner`。它按中文关键词判断动作，适合检查网页、检定、线索和存档能否连起来。**它不是大模型，不能把这个模式当作最终的 LLM / RAG 效果展示。**未设置模式时默认使用这个方式，不会产生模型费用。

```sh
export KP_MODEL_MODE=demo
```

支持当前地点的观察、调查、交谈、规则问答、移动、物品使用和结束调查。对“我检查一下”会追问；下一句回答具体对象时保留上一步的调查意图。回访仍保留调查进度；“阅读来信”“查看照片”等只读已经获得的内容。无法可靠理解的输入会追问或提示当前不支持。

## 先接 DeepSeek 官方 API

先装好项目依赖，把项目根目录 `.env.example` 复制为 `.env`，在本机填写：

```dotenv
DEEPSEEK_API_KEY=在这里填写自己的key
DEEPSEEK_MODEL=deepseek-flash
DEEPSEEK_REASONING_EFFORT=none
DEEPSEEK_PLAN_MAX_TOKENS=1024
DEEPSEEK_NARRATION_MAX_TOKENS=2048
KP_RETRIEVAL_MODE=keyword
```

真实 key 只填自己的 `.env`，不用发给聊天或群里。`.env` 已被 Git 忽略。
程序会自动读取项目根目录这份文件，不执行其中的 shell 命令；终端中已设置的同名变量优先。
本机 `.env` 权限设为 `0600`，已有文件不会被覆盖。修改 `.env` 后退出并重新启动程序才会生效。

macOS 可以双击 `run_deepseek.command`，也可以运行：

```sh
.venv/bin/python -m kp_agent --mode deepseek --db saves/deepseek.sqlite3
```

这个启动方式明确选择 DeepSeek，使用 `https://api.deepseek.com`。不需要填写 `OPENAI_API_KEY`。
`.env.example` 的 `KP_MODEL_MODE=demo` 是安全的离线默认；不带 `--mode` 时才按照该设置选择。
`run_demo.command` 始终是离线演示，不会因为已经填 key 就自动联网。

DeepSeek 启动器使用 `saves/deepseek.sqlite3`，和离线默认存档分开。再次打开会继续原存档，
不是自动开始新局；本局结束后输入 `/restart`。更新代码后，要先退出旧终端，再重新启动。

本次真实调用使用 `DEEPSEEK_MODEL=deepseek-flash`，模型名与实际返回值记录在调用元数据里。
这轮没有比较其他模型，也不把本次结果推广为所有模型、所有口语都能正确处理。

| 设置 | 当前默认 | 含义 |
|---|---|---|
| `DEEPSEEK_REASONING_EFFORT` | `none` | 关闭思考，减少等待；也可选 `low`、`high`、`max` |
| `DEEPSEEK_PLAN_MAX_TOKENS` | `1024` | 理解行动这次请求的输出上限，包含思考 token |
| `DEEPSEEK_NARRATION_MAX_TOKENS` | `2048` | 公开叙述这次请求的输出上限，包含思考 token |

Responses API 使用 `reasoning.effort` 控制思考，不使用 Chat Completions 的 `thinking` 参数。
普通行动通常包含 `plan` 和 `narrate` 两次调用；追问通常只调用 `plan`。
成功等级的数值算例改由只读工具 `success_example` 使用已有检定引擎生成，并直接显示本次规则引用，
不交给 `narrate` 重写，因此这类问答通常只有一次 `plan`。假想出目不是实际掷骰，不改变角色资源。
其他叙事继续使用模型。
DeepSeek 设置 `max_retries=0`，不在后台自动重试；失败时由玩家输入 `/retry` 恢复原消息。
先保持关键词规则检索，等主持流程能正常工作后再考虑向量检索。

调用记录放在 `saves/model_calls.jsonl`，只记录时间、模型、阶段和 token 用量，
不保存密钥、原始提示词或完整思考内容，可用于观察消耗。
token 数据来自 API 返回，失败时如果没有返回用量就记为 `null`，不能把这份记录当作精确账单。

本次 v2 的记录见 [泛化测试结果](泛化测试结果_2026-10-21.md)，不要与 v1 的旧书房记录混用。
当前 98 项离线测试全通过（原 60 项＋提示和行动安全补充 38 项）；首轮 23 条真实规划，模型原始规划和应用侧各通过 21 条，
同组关键词 demo 通过 14 条。修复后仅定向重查 4 条，模型原始规划 3/4、应用侧 4/4；
其中错误物品目标仍需程序改成追问。没有完整重跑首轮 23 条。

另做了真实 `KeeperService` 两回合、4 次 API 的整轮检查，8 项结构检查通过，
人工仍发现规则说明中的“30≤27”错误。改成程序直接生成数值算例后，
用 1 次 `plan`、0 次 `narrate` 做了 6 项检查，通过。结构正确不代表语言中的数学一定正确。

此前归档的模型检查合计 33 次 API：探测 1、首轮规划 23、定向规划 4、整轮检查 4、数值修复检查 1。
之后的提示和行动安全修复只做离线／假响应验证，未重跑真实模型；用户自行试玩用量另计。
没有自动重试。自由表达组是人工构造进度的规划检查，不代表随机完整跑团已经通关。
缺少配置会明确报错，不会悄悄切回离线或改用其他服务。失败后用 `/retry` 恢复原消息，
不要另外重复发送行动，以免把“重试请求”和“再做一次行动”混在一起。


## 怎样再查自由表达

`scripts/generalization_eval.py` 现在包含 25 例，默认 `demo`，默认最多 25 次规划。
g24、g25 是首轮发现错误物品用法后补充的例子，不能把它们算进最初的 23 条。
每次使用新的输出目录。离线命令不调用付费模型：

```sh
.venv/bin/python scripts/generalization_eval.py --mode demo --output output/qa/generalization_demo_new
```

下面的 DeepSeek 定向命令会产生费用，最多调用 4 次，每例只调用一次 `plan`：

```sh
.venv/bin/python scripts/generalization_eval.py --mode deepseek --case-ids g06,g11,g24,g25 --max-calls 4 --output output/qa/generalization_targeted_new
```

可用 `--case-ids` 按逗号筛选编号。达到上限或遇到认证、余额、限流、连接、超时等环境错误会停止，
保留部分报告；格式或目标校验失败会记为失败，不自动重新问模型。
输出分别记录 `raw_model_plan`、最终 `plan`、`raw_model_pass`、`application_pass` 和 `guard_adjusted`，
前者捕获于结构化解析之后、应用保护之前；格式尚未解析成功时原始规划为空。
耗时和 token 只汇总 API 元数据，不推算费用，不保存密钥、提示词或思考正文。

## 保留的 OpenAI 接法

如果之后需要使用 OpenAI，在本机配置：

```dotenv
OPENAI_MODEL=你们实际选择并有权限使用的模型名
OPENAI_API_KEY=在本机填写自己的key
```

再使用 `--mode openai`。可选 `OPENAI_BASE_URL` 只用于明确需要的兼容地址；
服务必须支持 Responses API 和相应 JSON Schema，只有 Chat Completions 兼容还不够。

只使用 DeepSeek 时，不用设置这些 OpenAI 字段。模型接口和可选向量接口分开配置。

## Agent 调用方式

```python
planner = create_planner()
plan = planner.plan(player_text, public_context, history, pending_question)
# 然后由场景代码验证plan，再执行真正的骰子和存档函数。
# 一般叙事交给模型；成功等级数值算例由工具直接显示，不经过这一步。
reply = planner.narrate(player_text, public_facts, history)
```

规划结果只有 `intent`、`target_id`、`item_id`、`query`、`question`。它不含技能数值、伤害、SAN 变化或任意函数名；这些由场景和规则代码决定。`intent` 包含 `look/investigate/careful_search/talk/move/use_item/finish/rule_question/leave/clarify/unsupported`，目标取自当前公开目标，不再固定为第一间书房的六个对象。`use_item` 需要真实物品与合法目标；明确的历史重复用法只作已经使用过的说明。`careful_search` 只用于当前公开提供的耗时补查，不会重复给奖励或加时间。

`context` 使用公开目标、公开场景、角色数据。最终叙事只接收公开事件、真实骰子结果、状态变化、已揭示线索和已经检索到的规则。不要把完整秘密模组放进 `public_facts` 的字段中。

在线模式通过 `client.responses.create(..., text={"format": JSON_SCHEMA})` 取得完整响应，
再用 Pydantic 在本地校验 JSON。规划和叙述使用不同的结构。
提示词也明确要求只输出 JSON，防止兼容服务直接返回普通文字；格式错误会明确拒绝，
不会把不合格式的文字擅自当作合法结果。先接收响应再校验，也能保留失败请求的实际用量。
程序还检查目标和引用编号；`evidence_id` 必须来自本次检索，不能从旧聊天中带入过期来源。
没有依据时不能把回答当作已核实的规则。

结构化输出保证的是格式，不能保证剧情事实一定正确。隔离秘密资料、校验场景条件和限制状态修改仍由程序负责。模型出错时应保留已保存的检定结果，重试叙事不重新掷骰。

实现参照：[OpenAI 官方结构化输出文档](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)、
[DeepSeek Responses API](https://api-docs.deepseek.com/zh-cn/guides/responses_api/)、
[DeepSeek 思考模式](https://api-docs.deepseek.com/zh-cn/guides/thinking_mode/)、
[DeepSeek 当前模型说明](https://api-docs.deepseek.com/quick_start/pricing/)。
