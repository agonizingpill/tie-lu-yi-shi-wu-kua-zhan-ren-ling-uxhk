from typing import Any

from fastapi import HTTPException
from psycopg.types.json import Jsonb

from railway.db import connect
from railway.enums import BagState
from railway.models.ledger import append_event
from railway.models.seals import find_bag, set_custody
from railway.models.searches import get_search
from railway.security import matches_proof
from railway.services.allocation import (
    TERMINAL_STATUSES,
    advisory_lock,
    active_for_search,
    active_for_seal,
    call_payload,
    get_number,
    allocate_verification_numbers,
)
from railway.services.recall import check_scope

PROOF_MISMATCH_DETAIL = "私密特征不符，封袋未锁定"


class RejectedVerification(HTTPException):
    """HTTP-compatible rejection that also carries the replayable verdict body."""

    def __init__(self, payload: dict, status_code: int = 409):
        super().__init__(status_code=status_code, detail=payload.get("detail", PROOF_MISMATCH_DETAIL))
        self.payload = payload


def answer_from(body: Any) -> str:
    for name in ("answer", "proof", "private_mark", "code"):
        value = getattr(body, name, None)
        if value:
            return str(value)
    if isinstance(body, dict):
        return str(body.get("answer") or body.get("proof") or body.get("private_mark") or "")
    return ""


def _claim_payload(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "claim_id": row["id"],
        "search_id": row["search_id"],
        "seal_id": row["seal_id"],
        "pickup_station": row["pickup_station"],
        "station_code": row["pickup_station"],
        "status": row["status"],
        "state": row["status"],
    }


def _stored_payload(row, *, default_status: int):
    status_code = row.get("response_status") or default_status
    body = row.get("response_body") if hasattr(row, "get") else None
    if body is None:
        body = call_payload(row)
    return status_code, body


def _complete_number(db, row_id: int, *, status: str, status_code: int, payload: dict,
                     actor: str, claim_id: int | None = None) -> None:
    if status == "verified":
        db.execute("""
            UPDATE verification_numbers
            SET status = %s, claim_id = COALESCE(%s, claim_id), verified_by = %s,
                verified_at = now(), response_status = %s, response_body = %s, updated_at = now()
            WHERE id = %s
        """, (status, claim_id, actor, status_code, Jsonb(payload), row_id))
    else:
        db.execute("""
            UPDATE verification_numbers
            SET status = %s, rejected_by = %s, rejected_at = now(),
                response_status = %s, response_body = %s, updated_at = now()
            WHERE id = %s
        """, (status, actor, status_code, Jsonb(payload), row_id))


def _success_payload(db, claim, number_row=None) -> dict[str, Any]:
    payload = _claim_payload(claim)
    if number_row is not None:
        number = number_row["id"]
        payload.update({
            "verification_id": number,
            "verification_no": number,
            "verification_number": number,
            "ticket_id": number,
            "ticket_no": number,
            "ticket_number": number,
            "call_id": number,
            "call_no": number,
            "call_number": number,
            "queue_number": number,
            "no": number,
            "number": number,
        })
    return payload


def _reject_pair_and_reallocate(db, *, search_id: int, seal_id: str, actor: str,
                                number_row=None) -> dict:
    db.execute("""
        INSERT INTO verification_rejections
            (search_id, seal_id, verification_id, rejected_by, reason)
        VALUES (%s, %s, %s, %s, 'proof_mismatch')
        ON CONFLICT (search_id, seal_id) DO NOTHING
    """, (search_id, seal_id, number_row["id"] if number_row else None, actor))
    append_event(db, seal_id, actor, "proof_rejected",
                 f"线索单 {search_id} 的私密特征不符，该线索-封袋对以后跳过并重新排号")

    if number_row is not None and number_row["status"] not in TERMINAL_STATUSES:
        # Store a provisional verdict; the response snapshot is finalized after
        # reallocation so callers can immediately see the replacement number.
        db.execute("""
            UPDATE verification_numbers
            SET status = 'rejected', rejected_by = %s, rejected_at = now(), updated_at = now()
            WHERE id = %s
        """, (actor, number_row["id"]))

    created = allocate_verification_numbers(db, actor_email=actor)
    next_row = active_for_search(db, search_id)
    next_number = call_payload(next_row)
    reallocated = [call_payload(row) for row in created]
    body = {
        "detail": PROOF_MISMATCH_DETAIL,
        "result": "rejected",
        "verdict": "rejected",
        "search_id": search_id,
        "seal_id": seal_id,
        "verification_id": number_row["id"] if number_row else None,
        "verification_no": number_row["id"] if number_row else None,
        "verification_number": number_row["id"] if number_row else None,
        "ticket_id": number_row["id"] if number_row else None,
        "ticket_no": number_row["id"] if number_row else None,
        "ticket_number": number_row["id"] if number_row else None,
        "call_id": number_row["id"] if number_row else None,
        "call_no": number_row["id"] if number_row else None,
        "call_number": number_row["id"] if number_row else None,
        "next": next_number,
        "next_verification": next_number,
        "next_ticket": next_number,
        "current_verification": next_number,
        "reallocated": reallocated,
        "reallocated_numbers": reallocated,
    }
    if number_row is not None:
        _complete_number(db, number_row["id"], status="rejected", status_code=409,
                         payload=body, actor=actor)
    return body


def _insert_claim(db, *, search_id: int, seal_id: str, station_code: str, actor: str):
    claim = db.execute("""
        INSERT INTO claims (search_id, seal_id, pickup_station, status, verified_by)
        VALUES (%s, %s, %s, 'verified', %s)
        RETURNING id, search_id, seal_id, pickup_station, status
    """, (search_id, seal_id, station_code, actor)).fetchone()
    set_custody(db, seal_id, BagState.RESERVED,
                db.execute("SELECT current_station FROM sealed_bags WHERE seal_id = %s",
                           (seal_id,)).fetchone()["current_station"])
    append_event(db, seal_id, actor, "claim_verified",
                 f"线索单 {search_id} 私密特征通过，封袋锁定")
    return claim


def verify_number(number_id: int, body: Any, user: dict):
    answer = answer_from(body)
    rejection: tuple[int, dict] | None = None
    with connect() as db:
        advisory_lock(db)
        number_row = get_number(db, number_id, lock=True)
        search = get_search(db, number_row["search_id"], lock=True)
        check_scope(search, user)

        if number_row["status"] in ("verified", "completed"):
            _, payload = _stored_payload(number_row, default_status=201)
            return payload
        if number_row["status"] in TERMINAL_STATUSES:
            rejection = _stored_payload(number_row, default_status=409)
        else:
            bag = find_bag(db, number_row["seal_id"], lock=True)
            hit = db.execute("""
                SELECT auditable FROM recall_hits
                WHERE search_id = %s AND seal_id = %s
            """, (number_row["search_id"], number_row["seal_id"])).fetchone()
            if not hit or not hit["auditable"]:
                raise HTTPException(409, "缺少可核对的公开词证据，单凭哈希候选不得认领")

            search_claim = db.execute("SELECT * FROM claims WHERE search_id = %s",
                                     (number_row["search_id"],)).fetchone()
            seal_claim = db.execute("SELECT * FROM claims WHERE seal_id = %s",
                                    (number_row["seal_id"],)).fetchone()
            if search_claim and search_claim["seal_id"] != number_row["seal_id"]:
                raise HTTPException(409, "本线索单已认领另一封袋")
            if seal_claim and seal_claim["search_id"] != number_row["search_id"]:
                raise HTTPException(409, "封袋已锁给其他认领或已交付")
            if bag["state"] != BagState.SEALED and not (search_claim or seal_claim):
                raise HTTPException(409, "封袋已锁给其他认领或已交付")

            if matches_proof(number_row["seal_id"], answer, bag["proof_digest"]):
                claim = search_claim or seal_claim
                if claim is None:
                    claim = _insert_claim(
                        db,
                        search_id=number_row["search_id"],
                        seal_id=number_row["seal_id"],
                        station_code=number_row["station_code"],
                        actor=user["email"],
                    )
                payload = _success_payload(db, claim, number_row)
                _complete_number(db, number_row["id"], status="verified", status_code=201,
                                 payload=payload, actor=user["email"], claim_id=claim["id"])
                return payload

            rejection = (409, _reject_pair_and_reallocate(
                db,
                search_id=number_row["search_id"],
                seal_id=number_row["seal_id"],
                actor=user["email"],
                number_row=number_row,
            ))
    if rejection is not None:
        status_code, payload = rejection
        raise RejectedVerification(payload, status_code)


def verify_claim(body, user: dict):
    """Backward-compatible POST /claims entry point with durable replay."""
    # If the client supplies a called number, that path owns the state machine.
    number_id = getattr(body, "ticket_id", None) or getattr(body, "verification_id", None) \
        or getattr(body, "call_id", None) or getattr(body, "verification_no", None) \
        or getattr(body, "ticket_no", None) or getattr(body, "call_no", None) \
        or getattr(body, "number", None)
    if number_id is not None:
        try:
            number_id = int(number_id)
        except (TypeError, ValueError):
            raise HTTPException(422, "核验号必须是整数")
        result = verify_number(number_id, body, user)
        if isinstance(result, dict):
            if result.get("search_id") != body.search_id or result.get("seal_id") != body.seal_id:
                raise HTTPException(409, "请求的线索或封袋与当前核验号不一致")
        return result

    direct_rejection: dict | None = None
    with connect() as db:
        advisory_lock(db)
        bag = find_bag(db, body.seal_id, lock=True)
        search = get_search(db, body.search_id, lock=True)
        check_scope(search, user)
        hit = db.execute("SELECT auditable FROM recall_hits WHERE search_id = %s AND seal_id = %s",
                         (body.search_id, body.seal_id)).fetchone()
        if not hit or not hit["auditable"]:
            raise HTTPException(409, "缺少可核对的公开词证据，单凭哈希候选不得认领")

        existing = db.execute("""
            SELECT id, search_id, seal_id, pickup_station, status
            FROM claims WHERE search_id = %s AND seal_id = %s
        """, (body.search_id, body.seal_id)).fetchone()
        if existing:
            number_row = db.execute("""
                SELECT * FROM verification_numbers
                WHERE search_id = %s AND seal_id = %s ORDER BY id DESC LIMIT 1
            """, (body.search_id, body.seal_id)).fetchone()
            payload = _success_payload(db, existing, number_row)
            if number_row and number_row["status"] != "verified":
                _complete_number(db, number_row["id"], status="verified", status_code=201,
                                 payload=payload, actor=user["email"], claim_id=existing["id"])
            return payload

        if db.execute("SELECT 1 FROM claims WHERE search_id = %s", (body.search_id,)).fetchone():
            raise HTTPException(409, "本线索单已认领另一封袋")
        if db.execute("SELECT 1 FROM claims WHERE seal_id = %s", (body.seal_id,)).fetchone():
            raise HTTPException(409, "封袋已锁给其他认领或已交付")

        rejection = db.execute("""
            SELECT response_body FROM verification_rejections
            WHERE search_id = %s AND seal_id = %s
        """, (body.search_id, body.seal_id)).fetchone()
        if rejection:
            body_snapshot = rejection["response_body"] or {"detail": PROOF_MISMATCH_DETAIL}
            raise RejectedVerification(body_snapshot, 409)

        active_search = active_for_search(db, body.search_id, lock=True)
        if active_search and active_search["seal_id"] != body.seal_id:
            raise HTTPException(
                409,
                f"本线索当前核验号为 #{active_search['id']}，对应封袋 {active_search['seal_id']}，请按号核验",
            )
        active_seal = active_for_seal(db, body.seal_id, lock=True)
        if active_seal and active_seal["search_id"] != body.search_id:
            raise HTTPException(409, "该封袋的有效核验号已发给另一张线索单")

        if bag["state"] != BagState.SEALED:
            raise HTTPException(409, "封袋已锁给其他认领或已交付")

        number_row = active_search if active_search and active_search["seal_id"] == body.seal_id else None
        if matches_proof(body.seal_id, body.answer, bag["proof_digest"]):
            claim = _insert_claim(db, search_id=body.search_id, seal_id=body.seal_id,
                                  station_code=user["station_code"] or search["entered_at"],
                                  actor=user["email"])
            payload = _success_payload(db, claim, number_row)
            if number_row is not None:
                _complete_number(db, number_row["id"], status="verified", status_code=201,
                                 payload=payload, actor=user["email"], claim_id=claim["id"])
            else:
                db.execute("""
                    INSERT INTO verification_numbers
                        (search_id, seal_id, station_code, status, claim_id, called_by,
                         verified_by, verified_at, response_status, response_body)
                    VALUES (%s, %s, %s, 'verified', %s, %s, %s, now(), 201, %s)
                """, (body.search_id, body.seal_id, search["entered_at"], claim["id"],
                      user["email"], user["email"], Jsonb(payload)))
            return payload

        payload = _reject_pair_and_reallocate(
            db,
            search_id=body.search_id,
            seal_id=body.seal_id,
            actor=user["email"],
            number_row=number_row,
        )
        if number_row is None:
            # Preserve a durable verdict even when the clerk verified directly
            # without first requesting a number.
            row = db.execute("""
                INSERT INTO verification_numbers
                    (search_id, seal_id, station_code, status, called_by, rejected_by,
                     rejected_at, response_status, response_body)
                VALUES (%s, %s, %s, 'rejected', %s, %s, now(), 409, %s)
                ON CONFLICT (search_id, seal_id) DO NOTHING
                RETURNING id
            """, (body.search_id, body.seal_id, search["entered_at"], user["email"],
                  user["email"], Jsonb(payload))).fetchone()
            if row:
                number_id = row["id"]
                payload.update({
                    "verification_id": number_id,
                    "verification_no": number_id,
                    "verification_number": number_id,
                    "ticket_id": number_id,
                    "ticket_no": number_id,
                    "ticket_number": number_id,
                    "call_id": number_id,
                    "call_no": number_id,
                    "call_number": number_id,
                    "queue_number": number_id,
                    "no": number_id,
                    "number": number_id,
                })
                db.execute("UPDATE verification_numbers SET response_body = %s WHERE id = %s",
                           (Jsonb(payload), number_id))
        direct_rejection = payload

    if direct_rejection is not None:
        raise RejectedVerification(direct_rejection, 409)
