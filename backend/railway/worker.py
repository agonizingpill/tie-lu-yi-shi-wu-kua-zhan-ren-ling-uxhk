import logging
import sys
import time
from pathlib import Path

from railway.config import HEARTBEAT, QUEUE
from railway.db import redis
from railway.services.recall import queued_search_id, rank_search, record_failure

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("rail.worker")


def worker_loop():
    while True:
        search_id = None
        try:
            redis.set(HEARTBEAT, "ready", ex=15)
            if not Path("/exchange").is_dir():
                raise RuntimeError("共享交接卷未挂载")
            entry = redis.brpop(QUEUE, timeout=2)
            search_id = int(entry[1]) if entry else queued_search_id()
            if search_id is not None:
                rank_search(search_id)
        except Exception:
            log.exception("检索 worker 处理失败")
            if search_id is not None:
                try:
                    record_failure(search_id)
                except Exception:
                    log.exception("检索状态回写失败")
            time.sleep(2)


if __name__ == "__main__":
    if "--health" in sys.argv:
        sys.exit(0 if redis.get(HEARTBEAT) == "ready" else 1)
    worker_loop()
