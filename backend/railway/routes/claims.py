from fastapi import APIRouter, Depends, Request

from railway.db import connect
from railway.models.claims import list_claims
from railway.schemas import ClaimProof, ReleaseReceipt
from railway.security import actor, clerk
from railway.services.idempotency import run_idempotent
from railway.services.ownership import release_claim
from railway.services.verification_desk import verify_claim

router = APIRouter(prefix="/claims")


@router.get("")
def claims(user=Depends(actor)):
    with connect() as db:
        return list_claims(db)


@router.post("", status_code=201)
def claim(body: ClaimProof, request: Request, user=Depends(clerk)):
    return run_idempotent(
        request,
        body,
        user,
        lambda: verify_claim(body, user),
        success_status=201,
    )


@router.post("/{claim_id}/release")
def release(claim_id: int, body: ReleaseReceipt, user=Depends(clerk)):
    return release_claim(claim_id, body, user)
