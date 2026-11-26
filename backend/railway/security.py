from datetime import datetime, timedelta, timezone
from hashlib import pbkdf2_hmac
from hmac import compare_digest, digest
from secrets import token_hex

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from railway.config import PROOF_SECRET, TOKEN_SECRET
from railway.db import connect
from railway.enums import Role
from railway.text import normalized

bearer = HTTPBearer(auto_error=False)
JWT_SCOPE = "rail-lost-claim"


def password_hash(password: str, salt: str) -> str:
    return pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 210000).hex()


def new_password(password: str):
    salt = token_hex(16)
    return salt, password_hash(password, salt)


def authenticate(email: str, password: str):
    with connect() as db:
        user = db.execute("SELECT * FROM staff WHERE email = %s", (email.lower(),)).fetchone()
    if not user or not compare_digest(user["password_hash"], password_hash(password, user["salt"])):
        raise HTTPException(401, "账号或口令不正确")
    token = jwt.encode({
        "sub": user["email"],
        "aud": JWT_SCOPE,
        "exp": datetime.now(timezone.utc) + timedelta(hours=8),
    }, TOKEN_SECRET, algorithm="HS256")
    return {"token": token, "profile": profile(user)}


def profile(user):
    return {field: user[field] for field in ("email", "role", "station_code", "display_name")}


def actor(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials:
        raise HTTPException(401, "需要登录")
    try:
        payload = jwt.decode(credentials.credentials, TOKEN_SECRET, algorithms=["HS256"],
                             audience=JWT_SCOPE, options={"require": ["sub", "exp", "aud"]})
    except jwt.InvalidTokenError as exc:
        raise HTTPException(401, "会话已结束，请重新登录") from exc
    with connect() as db:
        user = db.execute("SELECT * FROM staff WHERE email = %s", (payload["sub"],)).fetchone()
    if not user:
        raise HTTPException(401, "账号不存在")
    return profile(user)


def clerk(user=Depends(actor)):
    if user["role"] != Role.CLERK:
        raise HTTPException(403, "需要站点柜员权限")
    return user


def dispatcher(user=Depends(actor)):
    if user["role"] != Role.DISPATCHER:
        raise HTTPException(403, "需要区段转运调度权限")
    return user


def proof_hash(seal_id: str, proof: str) -> str:
    proof_message = f"{seal_id}|{normalized(proof)}".encode()
    return digest(PROOF_SECRET.encode(), proof_message, "sha256").hex()


def matches_proof(seal_id: str, answer: str, expected: str) -> bool:
    return compare_digest(proof_hash(seal_id, answer), expected)
