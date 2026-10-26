> 历史材料：这是 ai-kp-v2／更早 CLI 阶段的记录，不是当前 main 的实现或测试总数。当前入口见[小组文档](../../README.md)。正文中的旧路径、命令和未完成事项按当时背景阅读；代码链接已改指当前目录供对照，不能据此当作旧代码快照。

# 组员共用 DeepSeek API

大家可以在各自电脑运行同一份代码，填提供的 Key。共用的是 API 额度；聊天、角色与存档仍分别保存在各自电脑。

DeepSeek 使用 API Key 鉴权，组员无需取得组长的账号密码。官方说明：[API 鉴权](https://api-docs.deepseek.com/api/deepseek-api/)。




## 组员怎样填写

1. 按 README 安装 Python 依赖。
2. 在 `ai-kp-v2` 文件夹中，把 `.env.example` 复制成 `.env`。已有 `.env` 时直接编辑，保留现有内容。
3. 用文本编辑器打开 `.env`，填写下面的设置，文件保存为 UTF-8：

```dotenv
DEEPSEEK_API_KEY=组长私下给你的Key
DEEPSEEK_MODEL=deepseek-flash
DEEPSEEK_REASONING_EFFORT=none
KP_RETRIEVAL_MODE=keyword
```

`KP_MODEL_MODE=demo` 可以保留，后面的 DeepSeek 启动文件会明确选择在线模式。

4. Mac 双击 `run_deepseek.command`，Windows 双击 `run_deepseek.bat`。

也可以从当前文件夹运行：

macOS / Linux：

```bash
.venv/bin/python -m kp_agent --mode deepseek --db saves/deepseek.sqlite3
```

Windows PowerShell：

```powershell
.\.venv\Scripts\python.exe -m kp_agent --mode deepseek --db saves/deepseek.sqlite3
```

更改 Key 后退出并重新打开程序。确认开头显示“DeepSeek 大模型模式”，就使用了在线模型；`run_demo` 仍然是离线演示。

## 和网页同学怎么接

以后接 FastAPI 时，Key 放运行 Python 后端的电脑环境中。React 通过后端发聊天请求，前端配置、网页源码和浏览器存储里不需要 Key。
当前 Agent 代码会读取后端的 `DEEPSEEK_API_KEY`；Python 调用方法见 `interfaces.md`。

多人共用 Key 时，API 额度共同消耗。各自本机的 `saves/model_calls.jsonl` 可查看本机调用量；账号总用量以平台为准。
报 401 时核对 Key，402 时由组长检查余额，429 时稍后重试原消息。不要把含 Key 的配置文件或截图贴到 GitHub。
