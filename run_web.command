#!/bin/zsh
set -e
TASK_ROOT="$(cd "$(dirname "$0")" && pwd)"
exec "$TASK_ROOT/backend/.venv/bin/python" "$TASK_ROOT/run_web.py"
