#!/bin/zsh
cd -- "$(dirname -- "$0")" || exit 1
if [[ ! -x .venv/bin/python ]]; then
  print '请先按照 README.md 创建 .venv 并安装 requirements-agent.txt。'
  read '?按回车关闭。'
  exit 1
fi
exec .venv/bin/python -m kp_agent --mode demo "$@"
