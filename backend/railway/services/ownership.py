from fastapi import HTTPException

from railway.db import connect
from railway.enums import BagState, ClaimState
from railway.models.claims import get_claim
from railway.models.ledger import append_event
from railway.models.searches import get_search
from railway.models.seals import find_bag, set_custody
from railway.security import matches_proof
from railway.services.recall import check_scope


def verify_claim(body, user):
    # The durable implementation lives in verification_desk so ticket-based
    # verification, direct /claims compatibility, replay and reallocation share
    # one state machine.
    from railway.services.verification_desk import verify_claim as _verify_claim

    return _verify_claim(body, user)


def release_claim(claim_id, body, user):
    with connect() as db:
        claim = get_claim(db, claim_id)
        bag = find_bag(db, claim["seal_id"], lock=True)
        if claim["pickup_station"] != user["station_code"]:
            raise HTTPException(403, "仅约定取件站可交付")
        if body.scanned_seal != bag["seal_id"]:
            raise HTTPException(409, "扫描封签与认领单不符")
        if bag["current_station"] != user["station_code"] or bag["state"] != BagState.RESERVED:
            raise HTTPException(409, "封袋尚未到站或已经交付")
        db.execute("""
            UPDATE claims SET status = 'released', released_by = %s, released_at = now() WHERE id = %s
        """, (user["email"], claim_id))
        set_custody(db, bag["seal_id"], BagState.RELEASED, user["station_code"])
        append_event(db, bag["seal_id"], user["email"], "released", f"认领单 {claim_id} 单次交付完成")
        return {"id": claim_id, "seal_id": bag["seal_id"], "status": ClaimState.RELEASED}
