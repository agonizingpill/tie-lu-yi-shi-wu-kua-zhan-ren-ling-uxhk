from datetime import timedelta

from fastapi import HTTPException
from psycopg.types.json import Jsonb
from redis.exceptions import RedisError

from railway.config import QUEUE
from railway.db import connect, redis
from railway.enums import SearchState
from railway.models.searches import get_search, hits
from railway.services.allocation import (
    allocate_verification_numbers,
    optimal_matching,
    optimal_pairs,
)


def check_scope(search, user):
    if user["station_code"] and search["entered_at"] != user["station_code"]:
        raise HTTPException(403, "跨站检索单需到受理站查看")


def create_search(body, user):
    with connect() as db:
        search = db.execute("""
            INSERT INTO search_slips (category, color, description, travel_on, train_no, entered_at, entered_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id, status
        """, (body.category, body.color, body.description, body.travel_on, body.train_no,
              user["station_code"], user["email"])).fetchone()
    try:
        redis.lpush(QUEUE, search["id"])
    except RedisError:
        # Persistent queued rows are recovered by the worker when Redis becomes reachable.
        pass
    return search


def detailed_search(search_id, user):
    from railway.services.allocation import active_for_search, call_payload

    with connect() as db:
        search = get_search(db, search_id)
        check_scope(search, user)
        candidates = hits(db, search_id)
        current = call_payload(active_for_search(db, search_id))
        for candidate in candidates:
            candidate["blocked"] = bool(candidate.get("proof_rejected"))
            candidate["rejected_pair"] = bool(candidate.get("proof_rejected"))
            candidate["is_current"] = bool(current and candidate.get("verification_id") == current["id"])
            candidate["current"] = candidate["is_current"]
        if current:
            search["current_verification_id"] = current["id"]
            search["current_verification_no"] = current["verification_no"]
            search["verification_id"] = current["id"]
            search["verification_no"] = current["verification_no"]
            search["ticket_id"] = current["id"]
            search["call_id"] = current["id"]
            search["assigned_seal_id"] = current["seal_id"]
            search["current_seal_id"] = current["seal_id"]
        bundle = {
            "search": search,
            "candidates": candidates,
            "current_verification": current,
            "current_ticket": current,
            "current_call": current,
            "verification": current,
            "ticket": current,
            "call": current,
            "verification_no": current and current["verification_no"],
        }
        return bundle


def queued_search_id():
    with connect() as db:
        row = db.execute("""
            SELECT id FROM search_slips WHERE status = 'queued' AND queued_at < now() - interval '5 seconds'
            ORDER BY queued_at LIMIT 1
        """).fetchone()
        return row and row["id"]


def rank_search(search_id):
    from railway.services.encoding import ALGORITHM, DIMENSIONS, score_clues

    with connect() as db:
        search = get_search(db, search_id, lock=True)
        if search["status"] != SearchState.QUEUED:
            return
        start = search["travel_on"]
        bags = db.execute("""
            SELECT seal_id, category, color, description, train_no FROM sealed_bags
            WHERE state = 'sealed' AND found_on BETWEEN %s AND %s ORDER BY seal_id LIMIT 3000
        """, (start - timedelta(days=1), start + timedelta(days=2))).fetchall()
        candidates = score_clues(search, bags)
        with db.cursor() as cursor:
            cursor.executemany("""
                INSERT INTO recall_hits (search_id, seal_id, rank, score, exact_features, collision_slots, auditable)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, [(search_id, hit["seal_id"], rank, hit["score"], hit["exact_features"],
                   hit["collision_slots"], hit["auditable"]) for rank, hit in enumerate(candidates, 1)])
        summary = Jsonb({"algorithm": ALGORITHM, "dimensions": DIMENSIONS, "compared": len(bags),
                         "returned": len(candidates), "usable": sum(hit["auditable"] for hit in candidates),
                         "collision_slots": sum(hit["collision_slots"] for hit in candidates)})
        db.execute("UPDATE search_slips SET status = 'ranked', model_summary = %s WHERE id = %s",
                   (summary, search_id))


def record_failure(search_id):
    with connect() as db:
        db.execute("""
            UPDATE search_slips SET status = 'failed'
            WHERE id = %s AND status = 'queued'
        """, (search_id,))


# Descriptive aliases used by different versions of the counter allocation spec.
allocate_matching = optimal_pairs
assign_matching = optimal_matching
assign_verification_numbers = allocate_verification_numbers
