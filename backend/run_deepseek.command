#!/bin/zsh
# Double-click to run the real model with its own saved game.
cd -- "$(dirname -- "$0")" || exit 1

if [[ ! -x .venv/bin/python ]]; then
  print '请先按照 README.md 创建 .venv 并安装 requirements-agent.txt。'
  if [[ -t 0 ]]; then
    read '?按回车关闭。'
  fi
  exit 1
fi

.venv/bin/python -m kp_agent --mode deepseek --db saves/deepseek.sqlite3 "$@"
result=$?
if (( result != 0 )); then
  print '\n启动或运行未完成。请检查依赖、项目 .env 中的 DeepSeek 设置，以及上面的错误提示。'
  if [[ -t 0 ]]; then
    read '?按回车关闭。'
  fi
fi
exit "$result"
