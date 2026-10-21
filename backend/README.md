# Backend

在此目录执行：

```sh
uv sync --locked
uv run --locked uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

CLI 使用 `uv run --locked python -m kp_agent --mode demo`。
环境模板为本目录 `.env.example`，个人配置为本目录 `.env`。

职责、测试和 Windows 步骤见[开发指南](../docs/development.md)，业务说明见[Agent 指南](../docs/agent-guide.md)。
