from fastapi import HTTPException


def list_claims(db):
    return db.execute("""
        SELECT c.id, c.search_id, c.seal_id, c.pickup_station, c.status,
               b.current_station, b.state AS bag_state, c.released_at, t.code AS transfer_code
        FROM claims c JOIN sealed_bags b USING (seal_id)
        LEFT JOIN transfers t ON t.claim_id = c.id
        ORDER BY c.id DESC LIMIT 200
    """).fetchall()


def get_claim(db, claim_id):
    claim = db.execute("SELECT * FROM claims WHERE id = %s", (claim_id,)).fetchone()
    if not claim:
        raise HTTPException(404, "未找到认领单")
    return claim
