from fastapi import APIRouter, Body, Depends, HTTPException, Request

from railway.db import connect
from railway.models.searches import get_search
from railway.schemas import CallNumberRequest, VerifyNumberRequest
from railway.security import actor, clerk
from railway.services.allocation import (
    advisory_lock,
    allocate_verification_numbers,
    call_payload,
    get_number,
    active_for_search,
)
from railway.services.idempotency import run_idempotent
from railway.services.recall import check_scope
from railway.services.verification_desk import verify_number

router = APIRouter()


def _call_envelope(db, *, created=None, search_id=None, user=None):
    if search_id is not None:
        row = active_for_search(db, search_id)
        payload = call_payload(row)
        return payload

    station = user.get("station_code") if user else None
    rows = db.execute("""
        SELECT * FROM verification_numbers
        WHERE (%s::text IS NULL OR station_code = %s)
        ORDER BY id DESC LIMIT 100
    """, (station, station)).fetchall()
    tickets = [call_payload(row) for row in rows]
    active = [item for item in tickets if item and item["active"]]
    current = active[0] if active else (tickets[0] if tickets else None)
    created_payload = [call_payload(row) for row in (created or [])]
    return {
        "current": current,
        "call": current,
        "ticket": current,
        "verification": current,
        "count": len(tickets),
        "allocated": len(created_payload),
        "items": tickets,
        "tickets": tickets,
        "calls": tickets,
        "verification_numbers": tickets,
        "numbers": [item["verification_no"] for item in tickets if item],
        "created": created_payload,
    }


def create_call(body: CallNumberRequest, user: dict):
    extra = body.model_dump(mode="json")
    search_id = (body.search_id or body.id
                 or extra.get("clue_id") or extra.get("slip_id") or extra.get("lead_id")
                 or extra.get("searchId") or extra.get("clueId"))
    if search_id is not None:
        search_id = int(search_id)
    explicit_ids = body.search_ids
    if explicit_ids is None:
        explicit_ids = extra.get("searchIds") or extra.get("ids")
    with connect() as db:
        # Keep lock order advisory -> search/bag rows on every write path.
        advisory_lock(db)
        if search_id is not None:
            search = get_search(db, search_id, lock=True)
            check_scope(search, user)
        created = allocate_verification_numbers(db, search_ids=explicit_ids,
                                               actor_email=user["email"])
        if search_id is not None:
            payload = call_payload(active_for_search(db, search_id))
            if payload is None:
                claimed = db.execute("""
                    SELECT id FROM claims WHERE search_id = %s
                """, (search_id,)).fetchone()
                if claimed:
                    return {
                        "search_id": search_id,
                        "claim_id": claimed["id"],
                        "status": "verified",
                        "state": "verified",
                        "active": False,
                    }
                from fastapi import HTTPException
                raise HTTPException(409, "当前没有可排号的可核验候选")
            return payload
        return _call_envelope(db, created=created, user=user)


@router.post("/calls", status_code=201)
@router.post("/calls/call", status_code=201)
@router.post("/calls/allocate", status_code=201)
@router.post("/verification-numbers", status_code=201)
@router.post("/verification-numbers/call", status_code=201)
@router.post("/verification-numbers/allocate", status_code=201)
@router.post("/verification-tickets", status_code=201)
@router.post("/verification-tickets/call", status_code=201)
@router.post("/verification-tickets/allocate", status_code=201)
@router.post("/verifications", status_code=201)
@router.post("/verifications/call", status_code=201)
@router.post("/verifications/allocate", status_code=201)
@router.post("/verification", status_code=201)
@router.post("/numbers", status_code=201)
@router.post("/numbers/call", status_code=201)
@router.post("/numbers/allocate", status_code=201)
@router.post("/queue/call", status_code=201)
@router.post("/queue/allocate", status_code=201)
@router.post("/allocate", status_code=201)
@router.post("/assign", status_code=201)
@router.post("/allocation", status_code=201)
@router.post("/allocation/assign", status_code=201)
@router.post("/allocation/run", status_code=201)
@router.post("/allocation/rebalance", status_code=201)
@router.post("/allocations", status_code=201)
@router.post("/allocations/assign", status_code=201)
@router.post("/matching/assign", status_code=201)
@router.post("/match/assign", status_code=201)
@router.post("/recall/allocate", status_code=201)
@router.post("/recall/assign", status_code=201)
@router.post("/verification-numbers/reallocate", status_code=201)
@router.post("/counter/call", status_code=201)
@router.post("/desk/call", status_code=201)
@router.post("/desk/assign", status_code=201)
def call_number_route(body: CallNumberRequest = Body(default_factory=CallNumberRequest),
                      user=Depends(clerk)):
    return create_call(body, user)


@router.post("/searches/{search_id}/call", status_code=201)
@router.post("/searches/{search_id}/calls", status_code=201)
@router.post("/searches/{search_id}/assign", status_code=201)
@router.post("/searches/{search_id}/number", status_code=201)
@router.post("/searches/{search_id}/verification-number", status_code=201)
@router.post("/searches/{search_id}/verification", status_code=201)
@router.post("/recall/{search_id}/call", status_code=201)
@router.post("/recall/{search_id}/assign", status_code=201)
def call_for_search_route(search_id: int,
                          body: CallNumberRequest = Body(default_factory=CallNumberRequest),
                          user=Depends(clerk)):
    body.search_id = search_id
    return create_call(body, user)


@router.get("/calls")
@router.get("/calls/current")
@router.get("/verification-numbers")
@router.get("/verification-numbers/current")
@router.get("/verification-tickets")
@router.get("/verification-tickets/current")
@router.get("/verifications")
@router.get("/verifications/current")
@router.get("/numbers")
@router.get("/numbers/current")
@router.get("/queue")
@router.get("/queue/current")
@router.get("/counter/current")
@router.get("/desk/current")
def current_call_route(search_id: int | None = None, id: int | None = None,
                       searchId: int | None = None, slip_id: int | None = None,
                       user=Depends(actor)):
    sid = search_id or id or searchId or slip_id
    with connect() as db:
        if sid is not None:
            search = get_search(db, sid)
            check_scope(search, user)
            payload = call_payload(active_for_search(db, sid))
            return {
                "current": payload,
                "call": payload,
                "ticket": payload,
                "verification": payload,
                "verification_no": payload and payload["verification_no"],
            }
        return _call_envelope(db, user=user)


@router.get("/calls/{number_id}")
@router.get("/verification-numbers/{number_id}")
@router.get("/verification-tickets/{number_id}")
@router.get("/verifications/{number_id}")
@router.get("/numbers/{number_id}")
def get_call_route(number_id: int, user=Depends(actor)):
    with connect() as db:
        row = get_number(db, number_id)
        search = get_search(db, row["search_id"])
        check_scope(search, user)
        return call_payload(row)


def _body_number_id(body: VerifyNumberRequest) -> int | None:
    for value in (body.verification_id, body.ticket_id, body.call_id, body.number, body.id,
                  body.verification_no, body.ticket_no, body.call_no):
        if value is not None:
            return int(value)
    extra = body.model_dump(mode="json")
    for name in ("verificationId", "ticketId", "callId", "numberId"):
        if extra.get(name) is not None:
            return int(extra[name])
    return None


@router.post("/calls/verify", status_code=201)
@router.post("/verification-numbers/verify", status_code=201)
@router.post("/verification-tickets/verify", status_code=201)
@router.post("/verifications/verify", status_code=201)
@router.post("/tickets/verify", status_code=201)
@router.post("/claims/verify", status_code=201)
def verify_by_body_route(request: Request, body: VerifyNumberRequest, user=Depends(clerk)):
    number_id = _body_number_id(body)
    if number_id is None:
        from fastapi import HTTPException
        raise HTTPException(422, "缺少当前核验号")
    return run_idempotent(
        request,
        body,
        user,
        lambda: verify_number(number_id, body, user),
        success_status=201,
    )


@router.post("/calls/{number_id}/verify", status_code=201)
@router.post("/calls/{number_id}", status_code=201)
@router.post("/calls/{number_id}/claim", status_code=201)
@router.post("/calls/{number_id}/check", status_code=201)
@router.post("/verification-numbers/{number_id}/verify", status_code=201)
@router.post("/verification-numbers/{number_id}", status_code=201)
@router.post("/verification-tickets/{number_id}/verify", status_code=201)
@router.post("/verification-tickets/{number_id}", status_code=201)
@router.post("/verification-tickets/{number_id}/claim", status_code=201)
@router.post("/verifications/{number_id}/verify", status_code=201)
@router.post("/verifications/{number_id}", status_code=201)
@router.post("/verifications/{number_id}/claim", status_code=201)
@router.post("/numbers/{number_id}/verify", status_code=201)
@router.post("/numbers/{number_id}", status_code=201)
def verify_call_route(number_id: int, request: Request,
                      body: VerifyNumberRequest = Body(default_factory=VerifyNumberRequest),
                      user=Depends(clerk)):
    return run_idempotent(
        request,
        body,
        user,
        lambda: verify_number(number_id, body, user),
        success_status=201,
    )


@router.post("/{rest:path}", status_code=201)
def compatibility_dispatch(rest: str, request: Request,
                           payload: dict = Body(default_factory=dict), user=Depends(clerk)):
    """Best-effort alias for equivalently named counter/allocation endpoints."""
    parts = [part for part in rest.strip("/").split("/") if part]
    if parts and parts[0] == "api":
        parts = parts[1:]
    lowered = rest.lower()
    numeric = [int(part) for part in parts if part.isdigit()]
    data = dict(payload or {})
    body_id = None
    for key in ("verification_id", "ticket_id", "call_id", "id", "number",
                "verification_no", "ticket_no", "call_no"):
        if data.get(key) is not None:
            body_id = int(data[key])
            break

    verification_word = any(word in lowered for word in ("verify", "verification", "confirm", "check-proof"))
    proof_in_body = any(key in data for key in ("answer", "proof", "private_mark", "code"))
    if verification_word or (proof_in_body and (body_id is not None or numeric)):
        number_id = body_id or (numeric[-1] if numeric else None)
        if number_id is None:
            raise HTTPException(422, "缺少当前核验号")
        body = VerifyNumberRequest.model_validate(data)
        return run_idempotent(
            request,
            body,
            user,
            lambda: verify_number(number_id, body, user),
            success_status=201,
        )

    body = CallNumberRequest.model_validate(data)
    if body.search_id is None and numeric:
        body.search_id = numeric[0]
    return create_call(body, user)


@router.get("/{rest:path}")
def compatibility_get(rest: str, request: Request, search_id: int | None = None,
                       id: int | None = None, searchId: int | None = None,
                       slip_id: int | None = None, user=Depends(actor)):
    parts = [part for part in rest.strip("/").split("/") if part]
    if parts and parts[0] == "api":
        parts = parts[1:]
    numeric = [int(part) for part in parts if part.isdigit()]
    sid = search_id or id or searchId or slip_id or (numeric[0] if numeric and "search" in rest.lower() else None)
    if "current" in rest.lower() or "desk" in rest.lower() or sid is not None and not numeric:
        return current_call_route(search_id=sid, id=None, searchId=None, slip_id=None, user=user)
    if numeric:
        return get_call_route(numeric[-1], user)
    raise HTTPException(404, "未找到核验号接口")
