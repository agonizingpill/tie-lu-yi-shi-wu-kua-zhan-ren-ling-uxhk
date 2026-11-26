def append_event(db, seal_id: str, actor: str, action: str, detail: str):
    db.execute("INSERT INTO custody_events (seal_id, actor, action, detail) VALUES (%s, %s, %s, %s)",
               (seal_id, actor, action, detail))


def read_events(db, seal_id: str):
    return db.execute("""
        SELECT e.id, e.action, e.detail, e.at, s.display_name AS actor
        FROM custody_events e JOIN staff s ON s.email = e.actor
        WHERE e.seal_id = %s ORDER BY e.id DESC LIMIT 50
    """, (seal_id,)).fetchall()
