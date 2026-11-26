from fastapi import APIRouter, Depends

from railway.db import connect
from railway.models.searches import visible_to
from railway.schemas import SearchClue
from railway.security import actor, clerk
from railway.services.recall import create_search, detailed_search

router = APIRouter(prefix="/searches")


@router.get("")
def list_searches(user=Depends(actor)):
    with connect() as db:
        return visible_to(db, user)


@router.post("", status_code=202)
def enter(body: SearchClue, user=Depends(clerk)):
    return create_search(body, user)


@router.get("/{search_id}")
def read(search_id: int, user=Depends(actor)):
    return detailed_search(search_id, user)
