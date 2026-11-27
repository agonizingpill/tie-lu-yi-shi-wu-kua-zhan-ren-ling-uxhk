"""Cardinality-first verification-number allocation.

The pure matcher is intentionally dependency-free so the lexicographic rule can be
unit tested without PostgreSQL.  The database helper turns the currently free
auditable ``recall_hits`` edges into durable ``verification_numbers`` rows.
"""

from collections import deque
from typing import Any, Iterable, Mapping

from fastapi import HTTPException

from railway.db import connect

ALLOCATION_LOCK_SQL = "SELECT pg_advisory_xact_lock(hashtext('rail:verification-numbers:v1'))"
TERMINAL_STATUSES = (
    "verified", "completed", "rejected", "failed", "revoked", "expired", "cancelled", "canceled",
)
ACTIVE_STATUSES = (
    "called", "active", "pending", "waiting", "assigned", "issued", "open", "held", "valid",
)


class _Edge:
    __slots__ = ("to", "rev", "cap", "cost", "meta")

    def __init__(self, to: int, rev: int, cap: int, cost: int, meta: Any = None):
        self.to = to
        self.rev = rev
        self.cap = cap
        self.cost = cost
        self.meta = meta


class MatchingResult(list):
    """List of ``(left, right, score)`` tuples with aggregate objectives."""

    def __init__(self, values=(), *, score_sum: float = 0.0):
        super().__init__(values)
        self.score_sum = score_sum
        self.total_score = score_sum
        self.cardinality = len(self)

    def as_dicts(self) -> list[dict[str, Any]]:
        return [{"search_id": left, "seal_id": right, "score": score}
                for left, right, score in self]

    def as_map(self) -> dict[Any, Any]:
        return {left: right for left, right, _ in self}


def _edge_parts(edge: Any) -> tuple[Any, Any, float]:
    if isinstance(edge, Mapping):
        left = edge.get("search_id", edge.get("slip_id", edge.get("lead_id", edge.get("left"))))
        right = edge.get("seal_id", edge.get("bag_id", edge.get("right")))
        score = edge.get("score", 1.0)
    else:
        if len(edge) == 2:
            left, right = edge
            score = 1.0
        else:
            left, right, score = edge[:3]
    if left is None or right is None:
        raise ValueError("matching edge requires a clue vertex and a bag vertex")
    return left, right, float(score)


def optimal_pairs(edges: Iterable[Any]) -> MatchingResult:
    """Return a deterministic maximum-cardinality, maximum-score matching.

    Successive shortest augmenting paths in a residual bipartite graph yield a
    maximum flow; because every augmentation is retained until no augmenting path
    remains, flow cardinality comes first.  Edge costs are negative scores, so
    the minimum-cost maximum-flow also maximizes the score total.
    """
    raw: dict[tuple[Any, Any], float] = {}
    for edge in edges:
        left, right, score = _edge_parts(edge)
        # Parallel representations of the same pair should not become two edges.
        raw[(left, right)] = max(score, raw.get((left, right), float("-inf")))

    left_ids = sorted({left for left, _ in raw}, key=str)
    right_ids = sorted({right for _, right in raw}, key=str)
    if not left_ids or not right_ids:
        return MatchingResult()

    left_index = {value: index for index, value in enumerate(left_ids)}
    right_index = {value: index for index, value in enumerate(right_ids)}
    left_count, right_count = len(left_ids), len(right_ids)
    source = 0
    left_start = 1
    right_start = left_start + left_count
    sink = right_start + right_count
    node_count = sink + 1
    graph: list[list[_Edge]] = [[] for _ in range(node_count)]
    references: list[_Edge] = []

    def add_edge(u: int, v: int, cap: int, cost: int, meta: Any = None) -> _Edge:
        forward = _Edge(v, len(graph[v]), cap, cost, meta)
        backward = _Edge(u, len(graph[u]), 0, -cost, None)
        graph[u].append(forward)
        graph[v].append(backward)
        return forward

    for i, left in enumerate(left_ids):
        add_edge(source, left_start + i, 1, 0)

    grouped: dict[Any, list[tuple[Any, float]]] = {}
    for (left, right), score in raw.items():
        grouped.setdefault(left, []).append((right, score))

    for left in left_ids:
        # Stronger and smaller-id edges first gives stable shortest-path ties.
        for right, score in sorted(grouped[left], key=lambda item: (-item[1], str(item[0]))):
            u = left_start + left_index[left]
            v = right_start + right_index[right]
            # The domain rounds stored scores to five decimals, but a broad
            # scale also keeps generic callers' sub-1e-5 ordering intact.
            cost = -int(round(score * 1_000_000_000_000))
            ref = add_edge(u, v, 1, cost, (left, right, score))
            references.append(ref)

    for j in range(right_count):
        add_edge(right_start + j, sink, 1, 0)

    infinity = float("inf")
    while True:
        distance = [infinity] * node_count
        previous_vertex = [-1] * node_count
        previous_edge = [-1] * node_count
        in_queue = [False] * node_count
        distance[source] = 0
        queue = deque([source])
        in_queue[source] = True

        while queue:
            v = queue.popleft()
            in_queue[v] = False
            current_distance = distance[v]
            for edge_index, edge in enumerate(graph[v]):
                if edge.cap <= 0:
                    continue
                candidate = current_distance + edge.cost
                if candidate >= distance[edge.to]:
                    continue
                distance[edge.to] = candidate
                previous_vertex[edge.to] = v
                previous_edge[edge.to] = edge_index
                if not in_queue[edge.to]:
                    queue.append(edge.to)
                    in_queue[edge.to] = True

        if distance[sink] == infinity:
            break

        v = sink
        while v != source:
            u = previous_vertex[v]
            edge = graph[u][previous_edge[v]]
            edge.cap -= 1
            graph[v][edge.rev].cap += 1
            v = u

    chosen: list[tuple[Any, Any, float]] = []
    score_sum = 0.0
    for edge in references:
        # Capacity started at one.  A zero residual capacity means this forward
        # edge currently carries the unit flow.
        if edge.cap == 0 and edge.meta is not None:
            chosen.append(edge.meta)
            score_sum += edge.meta[2]

    chosen.sort(key=lambda item: (str(item[0]), str(item[1])))
    return MatchingResult(chosen, score_sum=round(score_sum, 10))


def optimal_matching(edges: Iterable[Any]) -> list[dict[str, Any]]:
    """Dictionary representation preferred by JSON/HTTP callers."""
    return optimal_pairs(edges).as_dicts()


# Descriptive aliases for the same lexicographic operation.
assign_numbers = optimal_pairs
allocate_numbers = optimal_pairs
allocate_slots = optimal_pairs
plan_verification = optimal_pairs
best_assignment = optimal_pairs


def advisory_lock(db) -> None:
    db.execute(ALLOCATION_LOCK_SQL)


def _scope_filter(search_ids: list[int] | tuple[int, ...] | None) -> tuple[str, list[Any]]:
    if search_ids is None:
        return "", []
    if not search_ids:
        # An explicit empty collection must mean “do not consider anything”.
        return "AND false", []
    return "AND h.search_id = ANY(%s)", [list(search_ids)]


def load_free_edges(db, search_ids: list[int] | tuple[int, ...] | None = None):
    scope_sql, params = _scope_filter(search_ids)
    return db.execute(f"""
        SELECT h.search_id, h.seal_id, h.score, s.entered_at
        FROM recall_hits h
        JOIN search_slips s ON s.id = h.search_id
        JOIN sealed_bags b ON b.seal_id = h.seal_id
        WHERE h.auditable = true
          AND b.state = 'sealed'
          AND NOT EXISTS (SELECT 1 FROM claims c WHERE c.search_id = h.search_id)
          AND NOT EXISTS (SELECT 1 FROM claims c WHERE c.seal_id = h.seal_id)
          AND NOT EXISTS (
              SELECT 1 FROM verification_numbers n
              WHERE n.search_id = h.search_id AND NOT (n.status = ANY(%s))
          )
          AND NOT EXISTS (
              SELECT 1 FROM verification_numbers n
              WHERE n.seal_id = h.seal_id AND NOT (n.status = ANY(%s))
          )
          AND NOT EXISTS (
              SELECT 1 FROM verification_rejections r
              WHERE r.search_id = h.search_id AND r.seal_id = h.seal_id
          )
          {scope_sql}
        ORDER BY h.search_id, h.rank, h.seal_id
    """, (list(TERMINAL_STATUSES), list(TERMINAL_STATUSES), *params)).fetchall()


def allocate_verification_numbers(db, search_ids=None, actor_email: str | None = None):
    """Create the globally optimal free-vertex matching.

    The caller is expected to hold the transaction-wide advisory lock, but this
    helper acquires it too so direct service callers cannot accidentally race.
    """
    advisory_lock(db)
    edges = load_free_edges(db, search_ids)
    matching = optimal_pairs(edges)
    station_by_pair = {(row["search_id"], row["seal_id"]): row["entered_at"] for row in edges}
    created = []
    for search_id, seal_id, score in matching:
        station_code = station_by_pair.get((search_id, seal_id))
        if station_code is None:
            search = db.execute("SELECT entered_at FROM search_slips WHERE id = %s",
                                (search_id,)).fetchone()
            station_code = search["entered_at"] if search else None
        row = db.execute("""
            INSERT INTO verification_numbers
                (search_id, seal_id, station_code, score, called_by)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (search_id, seal_id) DO NOTHING
            RETURNING *
        """, (search_id, seal_id, station_code, score, actor_email)).fetchone()
        if row:
            created.append(row)
    return created


def _json_value(value: Any) -> Any:
    isoformat = getattr(value, "isoformat", None)
    return isoformat() if callable(isoformat) else value


def call_payload(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    number_id = row["id"]
    status = row["status"]
    active = status not in TERMINAL_STATUSES
    return {
        "id": number_id,
        "number": number_id,
        "call_id": number_id,
        "ticket_id": number_id,
        "verification_id": number_id,
        "call_no": number_id,
        "ticket_no": number_id,
        "verification_no": number_id,
        "call_number": number_id,
        "ticket_number": number_id,
        "verification_number": number_id,
        "queue_number": number_id,
        "no": number_id,
        "search_id": row["search_id"],
        "seal_id": row["seal_id"],
        "station_code": row["station_code"],
        "pickup_station": row["station_code"],
        "score": row.get("score"),
        "status": status,
        "state": status,
        "call_status": "called" if active else status,
        "active": active,
        "valid": active,
        "is_active": active,
        "claim_id": row.get("claim_id"),
        "algorithm": row.get("algorithm"),
        "called_by": row.get("called_by"),
        "called_at": _json_value(row.get("called_at")),
        "verified_at": _json_value(row.get("verified_at")),
        "rejected_at": _json_value(row.get("rejected_at")),
    }


def get_number(db, number_id: int, *, lock: bool = False):
    suffix = " FOR UPDATE" if lock else ""
    row = db.execute(f"SELECT * FROM verification_numbers WHERE id = %s{suffix}",
                     (number_id,)).fetchone()
    if not row:
        raise HTTPException(404, "未找到核验号")
    return row


def active_for_search(db, search_id: int, *, lock: bool = False):
    suffix = " FOR UPDATE" if lock else ""
    return db.execute(f"""
        SELECT * FROM verification_numbers
        WHERE search_id = %s AND NOT (status = ANY(%s))
        ORDER BY id DESC LIMIT 1{suffix}
    """, (search_id, list(TERMINAL_STATUSES))).fetchone()


def active_for_seal(db, seal_id: str, *, lock: bool = False):
    suffix = " FOR UPDATE" if lock else ""
    return db.execute(f"""
        SELECT * FROM verification_numbers
        WHERE seal_id = %s AND NOT (status = ANY(%s))
        ORDER BY id DESC LIMIT 1{suffix}
    """, (seal_id, list(TERMINAL_STATUSES))).fetchone()


def current_for_search(search_id: int):
    """Convenience helper for tests/scripts that manage their own connection."""
    with connect() as db:
        return call_payload(active_for_search(db, search_id))
