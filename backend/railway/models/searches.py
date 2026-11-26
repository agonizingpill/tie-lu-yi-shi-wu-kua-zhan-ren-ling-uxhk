from fastapi import HTTPException


def get_search(db, search_id, *, lock=False):
    suffix = " FOR UPDATE" if lock else ""
    search = db.execute("SELECT * FROM search_slips WHERE id = %s" + suffix, (search_id,)).fetchone()
    if not search:
        raise HTTPException(404, "未找到线索单")
    return search


def hits(db, search_id):
    return db.execute("""
        SELECT h.seal_id, h.score, h.rank, h.exact_features, h.collision_slots, h.auditable,
               b.category, b.color, b.train_no, b.state AS bag_state, b.current_station
        FROM recall_hits h JOIN sealed_bags b USING (seal_id)
        WHERE h.search_id = %s ORDER BY h.rank
    """, (search_id,)).fetchall()


def visible_to(db, user):
    return db.execute("""
        SELECT id, category, color, description, travel_on, train_no, entered_at, status, model_summary
        FROM search_slips WHERE entered_at = COALESCE(%s, entered_at) ORDER BY id DESC LIMIT 100
    """, (user["station_code"],)).fetchall()
