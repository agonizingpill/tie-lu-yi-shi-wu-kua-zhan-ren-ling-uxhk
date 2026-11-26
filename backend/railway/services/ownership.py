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
    with connect() as db:
        bag = find_bag(db, body.seal_id, lock=True)
        search = get_search(db, body.search_id, lock=True)
        check_scope(search, user)
        hit = db.execute("SELECT auditable FROM recall_hits WHERE search_id = %s AND seal_id = %s",
                         (body.search_id, body.seal_id)).fetchone()
        if not hit or not hit["auditable"]:
            raise HTTPException(409, "缺少可核对的公开词证据，单凭哈希候选不得认领")
        if bag["state"] != BagState.SEALED:
            raise HTTPException(409, "封袋已锁给其他认领或已交付")
        if db.execute("SELECT 1 FROM claims WHERE search_id = %s", (body.search_id,)).fetchone():
            raise HTTPException(409, "本线索单已认领另一封袋")
        if matches_proof(body.seal_id, body.answer, bag["proof_digest"]):
            claim = db.execute("""
                INSERT INTO claims (search_id, seal_id, pickup_station, status, verified_by)
                VALUES (%s, %s, %s, 'verified', %s) RETURNING id, seal_id, pickup_station, status
            """, (body.search_id, body.seal_id, user["station_code"], user["email"])).fetchone()
            set_custody(db, body.seal_id, BagState.RESERVED, bag["current_station"])
            append_event(db, body.seal_id, user["email"], "claim_verified",
                         f"线索单 {body.search_id} 私密特征通过，封袋锁定")
            return claim
        append_event(db, body.seal_id, user["email"], "proof_rejected",
                     f"线索单 {body.search_id} 的私密特征不符，封袋仍可核验")
    raise HTTPException(409, "私密特征不符，封袋未锁定")


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
