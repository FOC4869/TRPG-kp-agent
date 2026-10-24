@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0" || exit /b 1

if not exist ".venv\Scripts\python.exe" (
    echo 请先在 backend 目录执行 uv sync --locked，详见 ../docs/development.md。
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m kp_agent --mode deepseek --db "saves\deepseek.sqlite3" %*
set "KP_EXIT_CODE=%ERRORLEVEL%"
if not "%KP_EXIT_CODE%"=="0" (
    echo 启动或运行未完成，请检查依赖、项目 .env 中的 DeepSeek 设置和上面的错误提示。
    pause
)
exit /b %KP_EXIT_CODE%
