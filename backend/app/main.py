"""ASGI entry point: uv run uvicorn app.main:app --reload."""

from contextlib import asynccontextmanager
from fastapi import FastAPI

from .api.health import router as health_router
from .api.modules import router as modules_router

from .api.games import router as games_router

@asynccontextmanager
async def lifespan(app):
    yield
    runtime = getattr(app.state, 'game_runtime', None)
    if runtime:
        await runtime.close()
        app.state.game_runtime = None

app = FastAPI(title="TRPG KP API", version="0.2.0", lifespan=lifespan)
app.include_router(health_router, prefix="/api")
app.include_router(modules_router, prefix="/api")

app.include_router(games_router, prefix="/api")
