"""ASGI entry point: uv run uvicorn app.main:app --reload."""

from fastapi import FastAPI

from .api.health import router as health_router

app = FastAPI(title="TRPG KP API", version="0.1.0")
app.include_router(health_router, prefix="/api")
