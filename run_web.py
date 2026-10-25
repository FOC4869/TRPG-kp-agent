"""Start this copy's two local servers and stop both when the window closes."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import webbrowser

ROOT = Path(__file__).resolve().parent


def main():
    python = ROOT / "backend" / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    node = os.getenv("NODE_BINARY") or shutil.which("node")
    vite = ROOT / "frontend/node_modules/vite/bin/vite.js"
    if not python.is_file() or not vite.is_file() or not node:
        print("请先按 README 安装后端和前端依赖，再重新打开。")
        return 1
    children = []
    options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    env = {**os.environ, "PYTHONUTF8": "1",
           "OWNED_WEB_SAVES": str(ROOT / "backend/saves")}

    def stop(*_):
        for child in reversed(children):
            if child.poll() is None:
                try:
                    if os.name == "nt":
                        child.terminate()
                    else:
                        os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass

    signal.signal(signal.SIGINT, lambda *_: stop())
    signal.signal(signal.SIGTERM, lambda *_: stop())
    try:
        children.append(subprocess.Popen([str(python), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8011"], cwd=ROOT / "backend", env=env, **options))
        children.append(subprocess.Popen([node, str(vite), "--host", "127.0.0.1"], cwd=ROOT / "frontend", env=env, **options))
        print("网页：http://127.0.0.1:5175\n关闭此窗口或按 Ctrl+C 可停止这份副本。", flush=True)
        time.sleep(2)
        if all(child.poll() is None for child in children):
            webbrowser.open("http://127.0.0.1:5175")
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
        return next((child.returncode for child in children if child.returncode), 0)
    finally:
        stop()
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()


if __name__ == "__main__":
    sys.exit(main())
