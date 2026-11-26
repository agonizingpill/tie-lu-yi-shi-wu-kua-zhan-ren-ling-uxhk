from secrets import token_hex

from fastapi import HTTPException

from railway.db import connect
from railway.enums import BagState, TransferState
from railway.models.claims import get_claim
from railway.models.ledger import append_event
from railway.models.seals import find_bag, set_custody
from railway.models.transfers import get_transfer


def dispatch(body, user):
    with connect() as db:
        claim = get_claim(db, body.claim_id)
        bag = find_bag(db, claim["seal_id"], lock=True)
        origin, destination = bag["current_station"], claim["pickup_station"]
        if origin == destination:
            raise HTTPException(409, "同站认领直接交付，无需转运")
        if bag["state"] != BagState.RESERVED:
            raise HTTPException(409, "仅已核验并锁定的封袋可发运")
        code = "TR-" + token_hex(5).upper()
        db.execute("""
            INSERT INTO transfers (code, claim_id, from_station, to_station, carrier_train, dispatched_by)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (code, body.claim_id, origin, destination, body.carrier_train, user["email"]))
        set_custody(db, bag["seal_id"], BagState.IN_TRANSIT, origin)
        append_event(db, bag["seal_id"], user["email"], "dispatched",
                     f"{code} 随 {body.carrier_train} 从 {origin} 运往 {destination}")
        return {"code": code, "from_station": origin, "to_station": destination, "state": TransferState.DISPATCHED}


def receive(code, body, user):
    with connect() as db:
        transfer = get_transfer(db, code)
        claim = get_claim(db, transfer["claim_id"])
        bag = find_bag(db, claim["seal_id"], lock=True)
        station = user["station_code"]
        if station != transfer["to_station"]:
            raise HTTPException(403, "仅目标站柜员可收运")
        if bag["state"] != BagState.IN_TRANSIT or transfer["state"] != TransferState.DISPATCHED:
            raise HTTPException(409, "封袋已收运或当前状态不允许收运")
        if body.scanned_seal != bag["seal_id"]:
            raise HTTPException(409, "实扫封签与转运清单不符")
        db.execute("UPDATE transfers SET state = 'received', received_by = %s, received_at = now() WHERE code = %s",
                   (user["email"], code))
        set_custody(db, bag["seal_id"], BagState.RESERVED, station)
        append_event(db, bag["seal_id"], user["email"], "received", f"{station} 复扫封签接收 {code}")
        return {"code": code, "state": TransferState.RECEIVED, "current_station": station}
