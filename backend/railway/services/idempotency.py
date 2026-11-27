from hashlib import sha256
from json import dumps
from typing import Any, Callable

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response
from psycopg.types.json import Jsonb

from railway.db import connect


def idempotency_key(request: Request, body: Any | None = None) -> str | None:
    key = (request.headers.get("Idempotency-Key")
           or request.headers.get("X-Idempotency-Key")
           or request.headers.get("Idempotency-Token")
           or request.headers.get("X-Request-Id"))
    if not key and body is not None:
        for name in ("idempotency_key", "idempotency_token", "request_id", "request_token",
                     "client_token", "nonce", "key"):
            value = getattr(body, name, None)
            if value:
                key = value
                break
    return str(key).strip()[:200] if key else None


def _hash_body(request: Request, body: Any | None) -> str:
    if body is None:
        raw = b""
    elif hasattr(body, "model_dump"):
        raw = dumps(body.model_dump(mode="json"), sort_keys=True, ensure_ascii=False,
                    default=str).encode()
    elif isinstance(body, (dict, list)):
        raw = dumps(body, sort_keys=True, ensure_ascii=False, default=str).encode()
    else:
        raw = str(body).encode()
    digest = sha256()
    digest.update(request.method.encode())
    digest.update(b"\n")
    digest.update(request.url.path.encode())
    digest.update(b"\n")
    digest.update(raw)
    return digest.hexdigest()


def run_idempotent(
    request: Request,
    body: Any | None,
    user: dict,
    handler: Callable[[], Any],
    *,
    success_status: int = 200,
) -> Response:
    """Run handler once per user/key, replaying the stored verdict on retry."""
    key = idempotency_key(request, body)
    if not key:
        try:
            output = handler()
        except HTTPException as exc:
            payload = getattr(exc, "payload", {"detail": exc.detail})
            return JSONResponse(status_code=exc.status_code, content=payload)
        if isinstance(output, Response):
            return output
        return JSONResponse(status_code=success_status, content=output)

    request_hash = _hash_body(request, body)
    lock_name = f"rail:idempotency:{user['email']}:{key}"
    with connect() as control:
        # Serialize identical keys.  The transaction/control connection stays
        # open while handler() uses its own connection, so a concurrent retry
        # waits here and then reads the completed verdict.
        control.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (lock_name,))
        control.execute("""
            INSERT INTO idempotent_requests
                (user_email, idempotency_key, request_method, request_path, request_hash)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_email, idempotency_key) DO NOTHING
        """, (user["email"], key, request.method, request.url.path, request_hash))
        record = control.execute("""
            SELECT * FROM idempotent_requests
            WHERE user_email = %s AND idempotency_key = %s
            FOR UPDATE
        """, (user["email"], key)).fetchone()
        if record["request_hash"] != request_hash:
            raise HTTPException(409, "同一幂等键不能用于不同的核验请求")
        if record["status_code"] and record["response_body"] is not None:
            return JSONResponse(status_code=record["status_code"], content=record["response_body"])

        try:
            output = handler()
            if isinstance(output, JSONResponse):
                status_code = output.status_code
                payload = json_loads(output.body)
            elif isinstance(output, Response):
                status_code = output.status_code
                payload = {"detail": output.body.decode()}
            else:
                status_code = success_status
                payload = output
            control.execute("""
                UPDATE idempotent_requests
                SET status_code = %s, response_body = %s, completed_at = now()
                WHERE user_email = %s AND idempotency_key = %s
            """, (status_code, Jsonb(payload), user["email"], key))
        except HTTPException as exc:
            status_code = exc.status_code
            payload = getattr(exc, "payload", {"detail": exc.detail})
            control.execute("""
                UPDATE idempotent_requests
                SET status_code = %s, response_body = %s, completed_at = now()
                WHERE user_email = %s AND idempotency_key = %s
            """, (status_code, Jsonb(payload), user["email"], key))
            return JSONResponse(status_code=status_code, content=payload)

    return JSONResponse(status_code=status_code, content=payload)


def json_loads(body: bytes) -> Any:
    from json import loads

    return loads(body.decode())
