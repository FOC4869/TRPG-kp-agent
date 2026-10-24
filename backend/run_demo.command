#!/bin/zsh
cd -- "$(dirname -- "$0")" || exit 1
if [[ ! -x .venv/bin/python ]]; then
  print '请先在 backend 目录执行 uv sync --locked，详见 ../docs/development.md。'
  read '?按回车关闭。'
  exit 1
fi
exec .venv/bin/python -m kp_agent --mode demo "$@"
