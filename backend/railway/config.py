from os import environ

DATABASE_URL = environ.get("DATABASE_URL", "postgresql://rail:rail_local_database@127.0.0.1:17800/rail")
REDIS_URL = environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
TOKEN_SECRET = environ.get("TOKEN_SECRET", "rail-only-local-demo-jwt-change-before-sharing")
PROOF_SECRET = environ.get("PROOF_SECRET", "rail-only-local-demo-proof-change-before-sharing")
SEED_DEMO = environ.get("SEED_DEMO", "true").lower() == "true"
QUEUE = "rail:public-clue-search"
HEARTBEAT = "rail:ranking-heartbeat"
