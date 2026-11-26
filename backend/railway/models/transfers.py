from fastapi import HTTPException


def movements(db):
    return db.execute("""
        SELECT t.code, t.claim_id, c.seal_id, t.from_station, t.to_station, t.carrier_train,
               t.state, t.dispatched_at, t.received_at
        FROM transfers t JOIN claims c ON t.claim_id = c.id
        ORDER BY t.dispatched_at DESC LIMIT 200
    """).fetchall()


def get_transfer(db, code):
    row = db.execute("SELECT * FROM transfers WHERE code = %s", (code,)).fetchone()
    if not row:
        raise HTTPException(404, "未找到转运单")
    return row
