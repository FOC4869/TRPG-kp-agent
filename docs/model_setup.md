# 当前主版本的模型配置

## 网页模式

先按 [README](../README.md) 安装依赖。把 `backend/.env.example` 复制到同目录 `backend/.env`，已有文件直接编辑。

```dotenv
KP_WEB_MODEL_MODE=deepseek
DEEPSEEK_API_KEY=在本机填写自己的Key
DEEPSEEK_MODEL=deepseek-flash
DEEPSEEK_REASONING_EFFORT=none
DEEPSEEK_PLAN_MAX_TOKENS=1024
DEEPSEEK_NARRATION_MAX_TOKENS=2048
```

Key 只留在运行后端的电脑。React 调用自己的 FastAPI，不直接调用供应商。
本地环境读取不会覆盖终端已经设置的同名变量；改配置后重新启动后端。

根目录双击 `run_web.command`／`run_web.bat` 或运行 `python run_web.py`。
网页 5175、后端 8011。在线行动产生实际 API 用量。
将 `KP_WEB_MODEL_MODE=demo` 可运行离线关键词演示；它不是真实大模型效果。

代码里的 `DeepSeekResponsesPlanner` 调用官方 Responses 接口，使用结构化规划与流式叙述，
没有后台自动重试。真实返回模型和用量以日志为准。
本轮记录见 [调用元数据](evaluation/provider-call-metadata.json)，不是按回合数估算。

## 两种模式变量不要混用

- `KP_WEB_MODEL_MODE` 控制网页，当前网页默认 deepseek。
- `KP_MODEL_MODE` 或 CLI 的 `--mode` 控制原命令行流程，默认 demo。
- `KP_RETRIEVAL_MODE` 是原 CLI 检索配置入口；当前网页默认使用本地关键词检索，不通过这个变量自动切换 embedding。

CLI 示例需先进入 `backend/`：

```sh
uv run --locked python -m kp_agent --mode demo
uv run --locked python -m kp_agent --mode deepseek --db saves/deepseek.sqlite3
```

CLI SQLite 与网页 JSON 不互相复制。原版将 `.env` 放在 `ai-kp-v2/` 的说明只适用于历史版本。

## 记录与常见故障

默认调用元数据为本机 `backend/saves/model_calls.jsonl`；可用 `KP_MODEL_METRICS_PATH` 单独指定。
记录阶段、模型、耗时、token、解析结果及错误分类，不保存 Key、完整提示词或思考正文。
网页创建与读取游戏本身无需模型账号；发送在线行动时才需要有效配置。

401 检查 Key；402 检查供应商余额；429 保留原请求稍后恢复。
无效规划不会直接进入工具；当前可转为基于公开对象的追问。正文未完成按页面“恢复本轮”操作。
原始错误不会通过聊天回复公开。

## 组员在各自电脑使用

每个人安装同一版代码，在各自 `backend/.env` 填入获准使用的 Key。
共用 Key 只是共用供应商用量，人物、对话和存档不会因此同步。
这不构成多人联机；小组演示仍使用同一局单玩家角色。

当前代码也保留 OpenAI 模型与 embedding 适配入口，但本轮展示和实测使用 DeepSeek，
不应把保留的可选接口写成已做过同等实测的方案。
