# 2026-10-21 工程目录迁移

迁移基线：7aa25aa。当前代码统一至 frontend/backend。下表记录旧路径到新路径。

| 原路径 | 当前位置／处理 |
|---|---|
| 根 trpg/ 与 versions/ai-kp-v1/trpg/ | backend/trpg/，采用后者；6 个 Python 文件相同，character.py、rules.py、rules_store.py 为后续实现 |
| versions/ai-kp-v1/kp_agent/ | backend/kp_agent/ |
| 两份 data/ | backend/data/，采用发布子目录；rules_core.md 包含后续规则修正 |
| 两份 characters/ | backend/characters/，固定 XLSX 内容相同 |
| 根 tests/ 与发布子目录 tests/ | backend/tests/；同名 __init__.py 采用子目录，其余旧测试完整合并 |
| versions/ai-kp-v1/scripts/、run_* | backend/scripts/、backend/run_* |
| versions/ai-kp-v1/.env.example | backend/.env.example；注释中的配置目录更新 |
| versions/ai-kp-v1/docs/ | docs/，内部相对链接更新 |
| 根 DESIGN.md | docs/history/foundation-design.md，原始设计原文保留 |
| versions/ai-kp-v1/DESIGN.md | docs/agent-design.md |
| versions/ai-kp-v1/README.md、给组员_先看这里.md | docs/agent-guide.md、docs/team-guide.md，启动和路径说明更新 |
| versions/ai-kp-v1/SOURCE_SNAPSHOT.txt | docs/history/source-snapshot-7aa25aa.txt，原文与哈希保留，路径和校验只描述旧发布版 |
| requirements*.txt | 后续声明为 backend/pyproject.toml + uv.lock；原发布清单保存在本目录 published-requirements*.txt |
| versions/ai-kp-v1/ | 仅留 README 迁移指引 |
| 根 tests/trpg 下 19 个已跟踪 pyc | 从当前树移除，根 .gitignore 阻止缓存再次入库 |

## 业务行为与测试冲突

迁移保留产品业务逻辑、故事配置和角色卡内容；config.py 仅将缺少依赖时的旧 requirements 安装提示改为 backend 下的 uv sync --locked。
原根测试 test_rules.TestImprovement.test_improve 要求 improve(95, 96, 10) == 99，
后续版本 trpg/rules.py 及 data/rules_core.md 已采用核心规则书 PDF p79 / 书内 p71 的可超过 100 成长规则。
本轮保留后续实现，更新该旧断言为 105；不通过删除旧测试消除冲突。

原发布基线的 LangGraph、OpenAI SDK、Pydantic、dotenv、openpyxl 版本保持，新增 FastAPI 和 uvicorn，测试使用 httpx。
uv 首次解析选择了更高的 httpcore2/httpx2 间接版本，迁移以约束固定到原发布的 2.15.1，避免顺带更换模型客户端传输依赖。

## 历史证据解释

evaluation 中的日志、模型用量及截图是先前实验的证据，不代表本次重新调用了真实模型。
本目录原始设计及来源快照中的路径、版本和时间为当时语境；当前说明以 README 和 docs/architecture.md 为准。
真实本地 .env、旧虚拟环境和玩家存档不搬运，避免复制密钥或误用旧场景存档。

## 本轮验证（2026-10-21，macOS）

- `uv sync --locked`：通过，原模型主依赖基线保留。
- `uv run --locked python -m unittest discover -s tests -t . -q`：191 项通过（原底层、Agent 和新增 HTTP 骨架测试）。
- `python -m kp_agent --help`、离线 demo 单条消息及相同 message_id 重试：通过；使用临时数据库。
- 真实进程请求 `127.0.0.1:8000/api/health` 与经 Vite 的 `127.0.0.1:5173/api/health`：均为 200 与相同健康响应。
- Vite HTML 和 React 模块可访问；`npm ci`、lint、typecheck、build 通过。
- 比对 32 份原发布产品/脚本文件：除 config.py 的安装提示外内容一致；故事配置、角色卡未修改。
- 当前 Markdown 本地链接、Git 忽略规则和 diff 空白检查通过。
- 未运行：真实付费模型、真实 Windows、GitHub 托管 CI 和游戏网页联调；这些不属于本轮本地骨架验收。
