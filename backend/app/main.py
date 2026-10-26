"""FastAPI only transports public data to the owned Keeper workflow."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .api.health import router as health_router
from .api.modules import router as modules_router
from .api.games import router as games_router


@asynccontextmanager
async def lifespan(app):
    yield
    keeper = getattr(app.state, "web_keeper", None)
    if keeper is not None:
        await keeper.close()


app = FastAPI(title="COC Agent + RAG", version="0.3.0", lifespan=lifespan)
app.include_router(health_router, prefix="/api")
app.include_router(modules_router, prefix="/api")
app.include_router(games_router, prefix="/api")
