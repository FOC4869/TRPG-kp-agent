"""Read this checkout's optional .env without replacing shell variables."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_ENV_FILE = PROJECT_ROOT / ".env"


class LocalConfigurationError(ValueError):
    """Local configuration could not be loaded; never include file contents."""


def load_local_env() -> bool:
    """Load only PROJECT_ROOT/.env, keeping explicit environment values first.

    No upward filename search, string interpolation, or optional dependency
    import occurs when the file is absent. Repeated calls are harmless because
    existing process environment variables always take precedence.
    """
    try:
        if not LOCAL_ENV_FILE.exists():
            return False
    except OSError:
        raise LocalConfigurationError("无法检查项目的 .env 文件，请检查文件权限。") from None
    try:
        from dotenv import load_dotenv
        from dotenv.parser import parse_stream
    except ImportError:
        raise LocalConfigurationError("读取 .env 需要 python-dotenv，请先在 backend 目录执行 uv sync --locked。") from None
    try:
        # Validate first: python-dotenv otherwise emits warnings and silently
        # skips malformed lines. Keep those lines and their values private.
        with LOCAL_ENV_FILE.open("r", encoding="utf-8") as stream:
            if any(binding.error for binding in parse_stream(stream)):
                raise LocalConfigurationError("项目的 .env 格式不正确，请按“变量名=值”填写，并检查引号是否成对。")
        return bool(load_dotenv(
            dotenv_path=LOCAL_ENV_FILE,
            override=False,
            interpolate=False,
            encoding="utf-8",
        ))
    except LocalConfigurationError:
        raise
    except Exception:
        raise LocalConfigurationError("无法读取项目的 .env 文件，请检查文件权限、编码和格式。") from None
