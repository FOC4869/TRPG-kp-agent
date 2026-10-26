"""HTTP adaptation for the read-only public catalogue."""

from contextlib import contextmanager

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import ValidationError

from ..services.catalogue import (
    Catalogue, CatalogueNotFound, CatalogueUnavailable, InvestigatorCatalogue,
    InvestigatorDetail, ModulePage, PublicModule,
)

router = APIRouter(prefix='/modules', tags=['catalogue'])


def image_type(path):
    allowed = {'.svg': 'image/svg+xml', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
               '.png': 'image/png', '.webp': 'image/webp'}
    return allowed[path.suffix.lower()]


def get_catalogue() -> Catalogue:
    return Catalogue()


@contextmanager
def catalogue_errors():
    try:
        yield
    except CatalogueNotFound:
        raise HTTPException(404, 'Catalogue entry not found') from None
    except (CatalogueUnavailable, OSError, ValueError, TypeError, KeyError, IndexError, AttributeError, RecursionError, yaml.YAMLError, ValidationError):
        raise HTTPException(503, 'Catalogue temporarily unavailable') from None


@router.get('', response_model=ModulePage)
def list_modules(page: int = Query(1, ge=1), page_size: int = Query(3, ge=1, le=30), catalogue: Catalogue = Depends(get_catalogue)):
    with catalogue_errors():
        return catalogue.modules(page, page_size)


@router.get('/{module_id}', response_model=PublicModule)
def module_detail(module_id: str, catalogue: Catalogue = Depends(get_catalogue)):
    with catalogue_errors():
        return catalogue.module(module_id)


@router.get('/{module_id}/cover', response_class=FileResponse)
def module_cover(module_id: str, catalogue: Catalogue = Depends(get_catalogue)):
    with catalogue_errors():
        path = catalogue.cover(module_id)
        return FileResponse(path, media_type=image_type(path))


@router.get('/{module_id}/investigators', response_model=InvestigatorCatalogue)
def list_investigators(module_id: str, catalogue: Catalogue = Depends(get_catalogue)):
    with catalogue_errors():
        return catalogue.investigators(module_id)


@router.get('/{module_id}/investigators/{investigator_id}', response_model=InvestigatorDetail)
def investigator_detail(module_id: str, investigator_id: str, catalogue: Catalogue = Depends(get_catalogue)):
    with catalogue_errors():
        return catalogue.investigator(module_id, investigator_id)


@router.get('/{module_id}/investigators/{investigator_id}/portrait', response_class=FileResponse)
def investigator_portrait(module_id: str, investigator_id: str, catalogue: Catalogue = Depends(get_catalogue)):
    with catalogue_errors():
        path = catalogue.portrait(module_id, investigator_id)
        return FileResponse(path, media_type=image_type(path))
