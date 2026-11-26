from fastapi import APIRouter, Depends

from railway.db import connect
from railway.models.transfers import movements
from railway.schemas import ArrivalReceipt, DispatchRequest
from railway.security import actor, clerk, dispatcher
from railway.services.transport import dispatch, receive

router = APIRouter(prefix="/transfers")


@router.get("")
def transfers(user=Depends(actor)):
    with connect() as db:
        return movements(db)


@router.post("", status_code=201)
def send(body: DispatchRequest, user=Depends(dispatcher)):
    return dispatch(body, user)


@router.post("/{code}/receive")
def receive_transfer(code: str, body: ArrivalReceipt, user=Depends(clerk)):
    return receive(code, body, user)
