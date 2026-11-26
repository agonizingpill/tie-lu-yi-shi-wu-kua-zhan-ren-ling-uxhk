from fastapi import APIRouter, Depends

from railway.db import connect
from railway.models.seals import list_bags
from railway.schemas import NewSeal
from railway.security import actor, clerk
from railway.services.intake import bag_ledger, seal_item

router = APIRouter(prefix="/bags")


@router.get("")
def inventory(user=Depends(actor)):
    with connect() as db:
        return list_bags(db)


@router.post("", status_code=201)
def record(body: NewSeal, user=Depends(clerk)):
    return seal_item(body, user)


@router.get("/{seal_id}/ledger")
def ledger(seal_id: str, user=Depends(actor)):
    return bag_ledger(seal_id)
