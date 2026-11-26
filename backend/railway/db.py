from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from redis import Redis

from railway.config import DATABASE_URL, REDIS_URL

redis = Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=3, socket_timeout=4)


def connect():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=3)


def migrate():
    with connect() as db:
        for file in sorted(Path(__file__).resolve().parents[1].joinpath("migrations").glob("*.sql")):
            db.execute(file.read_text())
