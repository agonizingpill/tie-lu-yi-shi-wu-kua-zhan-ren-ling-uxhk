from fastapi import APIRouter, Depends

from railway.db import connect
from railway.schemas import Login
from railway.security import actor, authenticate

router = APIRouter()


@router.post("/auth/login")
def login(body: Login):
    return authenticate(body.email, body.password)


@router.get("/auth/profile")
def me(user=Depends(actor)):
    return user


@router.get("/stations")
def stations(user=Depends(actor)):
    with connect() as db:
        return db.execute("SELECT code, display_name, corridor_position FROM stations ORDER BY corridor_position").fetchall()
