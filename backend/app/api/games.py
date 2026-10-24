"""Thin HTTP adapter for the isolated web game runtime."""
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated
from uuid import UUID
import json
import os
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from ..services.catalogue import Catalogue, CatalogueNotFound, CatalogueUnavailable

router = APIRouter(prefix='/games', tags=['games'])

class CreateGame(BaseModel):
    model_config = ConfigDict(extra='forbid')
    requestId: UUID
    moduleId: str = Field(pattern=r'^[a-z0-9][a-z0-9_-]{0,79}$')
    investigatorId: str = Field(pattern=r'^[a-z0-9][a-z0-9_-]{0,79}$')

class Action(BaseModel):
    model_config = ConfigDict(extra='forbid')
    requestId: UUID
    text: str = Field(min_length=1, max_length=1000)
    expectedVersion: Annotated[int, Field(strict=True, ge=1)]
    confirmationId: UUID | None = None

    @field_validator('text')
    @classmethod
    def nonblank(cls, value):
        if not value.strip(): raise ValueError('Action cannot be blank')
        return value.strip()

@contextmanager
def game_errors():
    from kp_agent.gameplay.content import GameError
    try: yield
    except GameError as error:
        raise HTTPException(error.status, {'code': error.code, 'message': error.message}) from None
    except CatalogueNotFound:
        raise HTTPException(404, {'code': 'catalogue_not_found', 'message': '案件或人物不可用。'}) from None
    except (CatalogueUnavailable, OSError, ValueError, KeyError, TypeError):
        raise HTTPException(503, {'code': 'game_unavailable', 'message': '游戏资料或存储暂不可用；原文件已保留。'}) from None

async def get_runtime(request: Request):
    if not getattr(request.app.state, 'game_runtime', None):
        from kp_agent.gameplay.runtime import GameRuntime
        root = Path(os.getenv('WEB_GAME_SAVES', str(Path(__file__).resolve().parents[2] / 'saves')))
        with game_errors(): request.app.state.game_runtime = GameRuntime(Catalogue(), root)
    return request.app.state.game_runtime

@router.post('')
async def create_game(body: CreateGame, response: Response, runtime=Depends(get_runtime)):
    response.headers['Cache-Control'] = 'private, no-store'
    with game_errors(): return runtime.create(str(body.requestId), body.moduleId, body.investigatorId)

@router.get('/{game_id}')
async def get_game(game_id: str, response: Response, runtime=Depends(get_runtime)):
    response.headers['Cache-Control'] = 'private, no-store'
    with game_errors(): return runtime.get(game_id)

@router.post('/{game_id}/actions', response_class=StreamingResponse,
             responses={200: {'content': {'text/event-stream': {'schema': {'type': 'string'}}}}})
async def game_action(game_id: str, body: Action, runtime=Depends(get_runtime)):
    with game_errors(): job = await runtime.action(game_id, str(body.requestId), body.text, body.expectedVersion, str(body.confirmationId) if body.confirmationId else None)
    async def stream():
        async for event in job.stream():
            if event is None: yield ': heartbeat\n\n'
            else: yield f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
    return StreamingResponse(stream(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache, no-transform', 'X-Accel-Buffering': 'no'})

@router.get('/{game_id}/assets/{asset_id}')
async def game_asset(game_id: str, asset_id: str, runtime=Depends(get_runtime)):
    with game_errors():
        path, media = runtime.content.asset(runtime.read(game_id), asset_id)
        return FileResponse(path, media_type=media, headers={'Cache-Control': 'private, no-store'})
