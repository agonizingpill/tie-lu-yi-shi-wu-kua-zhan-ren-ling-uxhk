from fastapi import HTTPException
from psycopg.errors import UniqueViolation

from railway.db import connect
from railway.models.ledger import append_event, read_events
from railway.models.seals import find_bag, public_bag
from railway.security import proof_hash


def seal_item(body, user):
    station = user["station_code"]
    try:
        with connect() as db:
            bag = db.execute("""
                INSERT INTO sealed_bags (seal_id, origin_station, current_station, train_no,
                    found_on, category, color, description, proof_digest, recorded_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *
            """, (body.seal_id, station, station, body.train_no, body.found_on, body.category,
                  body.color, body.description, proof_hash(body.seal_id, body.private_mark), user["email"])).fetchone()
            append_event(db, body.seal_id, user["email"], "seal_created", f"{station} 站创建封袋")
    except UniqueViolation as exc:
        raise HTTPException(409, "封签号已使用，须换新封签") from exc
    return public_bag(bag)


def bag_ledger(seal_id):
    with connect() as db:
        return {"bag": public_bag(find_bag(db, seal_id)), "events": read_events(db, seal_id)}
