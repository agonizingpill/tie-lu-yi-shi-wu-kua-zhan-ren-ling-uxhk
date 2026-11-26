from contextlib import asynccontextmanager
from logging import getLogger

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from railway.config import SEED_DEMO
from railway.db import connect, migrate, redis
from railway.middleware import LoginQuota, RequestTrace
from railway.routes import bags, claims, search, session, transfers
from scripts.seed_demo import seed

log = getLogger("rail.startup")


@asynccontextmanager
async def lifespan(app):
    migrate()
    if SEED_DEMO:
        try:
            seed()
        except Exception:
            log.exception("演示数据初始化失败")
    yield


app = FastAPI(title="北砾铁路拾遗交接", lifespan=lifespan)
app.add_middleware(LoginQuota)
app.add_middleware(RequestTrace)
for module in (session, bags, search, claims, transfers):
    app.include_router(module.router)


@app.exception_handler(RequestValidationError)
async def validation_error(_, error):
    # FastAPI's standard structure includes inputs. Never echo a proof or password.
    issues = [{"field": ".".join(str(value) for value in item["loc"][1:]), "message": item["msg"]}
              for item in error.errors()]
    return JSONResponse({"detail": "输入不符合办理要求", "issues": issues}, status_code=422)


@app.get("/healthz")
def health():
    with connect() as db:
        db.execute("SELECT 1 FROM stations LIMIT 1")
    redis.ping()
    return {"status": "ok"}
