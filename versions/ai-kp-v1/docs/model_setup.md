# 模型怎么接

这个版本可以用离线演示、DeepSeek 官方 API，也保留 OpenAI API 的接法。

## 先用离线演示跑通

`KP_MODEL_MODE=demo` 使用 `DemoPlanner`。它按中文关键词判断动作，适合检查网页、检定、线索和存档能否连起来。**它不是大模型，不能把这个模式当作最终的 LLM / RAG 效果展示。**未设置模式时默认使用这个方式，不会产生模型费用。

```sh
export KP_MODEL_MODE=demo
```

支持观察房间、调查书桌/书架/壁炉、询问管家、查规则和离开。对“我检查一下”会追问；下一句回答“书桌”时保留上一步的调查意图。无法可靠理解的输入会追问或提示当前不支持。

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

**模型名字用 `deepseek-flash`。**当前官方文档把它指向 V4.1-Flash-1017；原 V4-Flash 已被升级，
旧 `deepseek-v4-flash` 名字也会使用新版，不能用旧名字固定旧模型。

| 设置 | 当前默认 | 含义 |
|---|---|---|
| `DEEPSEEK_REASONING_EFFORT` | `none` | 关闭思考，减少等待；也可选 `low`、`high`、`max` |
| `DEEPSEEK_PLAN_MAX_TOKENS` | `1024` | 理解行动这次请求的输出上限，包含思考 token |
| `DEEPSEEK_NARRATION_MAX_TOKENS` | `2048` | 公开叙述这次请求的输出上限，包含思考 token |

Responses API 使用 `reasoning.effort` 控制思考，不使用 Chat Completions 的 `thinking` 参数。
普通一轮通常包含 `plan` 和 `narrate` 两次调用；追问通常只调用 `plan`。
DeepSeek 设置 `max_retries=0`，不在后台自动重试；失败时由玩家输入 `/retry` 恢复原消息。
先保持关键词规则检索，等主持流程能正常工作后再考虑向量检索。

调用记录放在 `saves/model_calls.jsonl`，只记录时间、模型、阶段和 token 用量，
不保存密钥、原始提示词或完整思考内容，可用于观察消耗。
token 数据来自 API 返回，失败时如果没有返回用量就记为 `null`，不能把这份记录当作精确账单。

**2026-10-21 已完成真实 DeepSeek 联调。**相似对话和额外随机游戏检查通过；
记录放在 `output/qa/2026-10-21_repair_check/`。这只说明本轮案例通过，不能保证未来模型和网络永不出错。
缺少配置会明确报错，不会悄悄切回离线或改用其他服务。失败后用 `/retry` 恢复原消息，
不要另外重复发送行动，以免把“重试请求”和“再做一次行动”混在一起。

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
reply = planner.narrate(player_text, public_facts, history)
```

规划结果只有 `intent`、`target_id`、`query`、`question`。它不含技能数值、伤害、SAN 变化或任意函数名；这些由场景和规则代码决定。`intent` 包含 `look/investigate/careful_search/talk/rule_question/leave/clarify/unsupported`，目标限制为这次固定场景的六个对象。`careful_search` 只用于本场景公开提供的耗时补查；重复请求由场景说明已经完成，不能再次给奖励。

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
