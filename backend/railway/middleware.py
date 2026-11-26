from logging import getLogger
from time import perf_counter
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware

from railway.db import redis

log = getLogger("rail.access")


class RequestTrace(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace = uuid4().hex
        started = perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = trace
        response.headers["Cache-Control"] = "no-store"
        log.info("%s %s %s %d %.1fms", trace, request.method, request.url.path,
                 response.status_code, (perf_counter() - started) * 1000)
        return response


class LoginQuota(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/auth/login" and request.method == "POST":
            client = request.client.host if request.client else "unknown"
            key = f"rail:login-quota:{client}"
            try:
                with redis.pipeline() as pipe:
                    count, _ = pipe.incr(key).expire(key, 60, nx=True).execute()
            except RedisError:
                return JSONResponse({"detail": "暂时无法校验登录额度"}, status_code=503)
            if count > 40:
                return JSONResponse({"detail": "登录次数过多，请在一分钟后重试"},
                                    status_code=429, headers={"Retry-After": "60"})
        return await call_next(request)
