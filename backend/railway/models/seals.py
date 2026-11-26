from fastapi import HTTPException

PUBLIC_FIELDS = "seal_id, origin_station, current_station, train_no, found_on, category, color, description, state, recorded_at"


def find_bag(db, seal_id: str, *, lock=False):
    suffix = " FOR UPDATE" if lock else ""
    bag = db.execute("SELECT * FROM sealed_bags WHERE seal_id = %s" + suffix, (seal_id,)).fetchone()
    if not bag:
        raise HTTPException(404, "未找到封袋")
    return bag


def public_bag(bag):
    return {field: bag[field] for field in PUBLIC_FIELDS.split(", ")}


def list_bags(db):
    return db.execute(f"SELECT {PUBLIC_FIELDS} FROM sealed_bags ORDER BY found_on DESC, seal_id LIMIT 200").fetchall()


def set_custody(db, seal_id, state, station_code):
    db.execute("UPDATE sealed_bags SET state = %s, current_station = %s WHERE seal_id = %s",
               (state, station_code, seal_id))
