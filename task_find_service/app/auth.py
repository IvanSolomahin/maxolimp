import hashlib
import hmac
import json
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated
from urllib.parse import parse_qsl

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import User, UserSession

router = APIRouter(tags=["auth"])
COOKIE_NAME = "maxolimp_session"
SESSION_SECONDS = 30 * 24 * 60 * 60
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class Credentials(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=1024)


class InitDataPayload(BaseModel):
    initData: str


def verify_init_data(init_data: str, bot_token: str | None) -> dict | None:
    if not init_data or not bot_token:
        return None
    try:
        parsed_pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
        parsed = dict(parsed_pairs)
        if len(parsed) != len(parsed_pairs):
            return None
        received_hash = parsed.pop("hash")
        auth_date = int(parsed["auth_date"])
        if auth_date > time.time() + 60 or time.time() - auth_date > 3600:
            return None
        check_string = "\n".join(f"{key}={value}" for key, value in sorted(parsed.items()))
        secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, received_hash):
            return None
        user = json.loads(parsed["user"])
        if not isinstance(user, dict) or not isinstance(user.get("id"), int) or user["id"] <= 0:
            return None
        return user
    except (ValueError, KeyError, json.JSONDecodeError):
        return None


def normalized_email(email: str) -> str:
    value = email.strip().lower()
    if len(value) > 320 or not EMAIL_RE.fullmatch(value):
        raise HTTPException(status_code=422, detail="Invalid email")
    return value


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        name, n, r, p, salt, digest = stored.split("$")
        if name != "scrypt" or (int(n), int(r), int(p)) != (16384, 8, 1):
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(actual, bytes.fromhex(digest))
    except (ValueError, TypeError):
        return False


def user_view(user: User) -> dict:
    return {"id": user.id, "max_id": user.max_id, "email": user.email, "first_name": user.first_name}


async def issue_session(db: AsyncSession, response: Response, user: User) -> dict:
    token = secrets.token_urlsafe(32)
    await db.execute(delete(UserSession).where(UserSession.expires_at <= func.now()))
    db.add(UserSession(
        user_id=user.id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=SESSION_SECONDS),
    ))
    await db.commit()
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_SECONDS, httponly=True, secure=True, samesite="lax", path="/")
    return user_view(user)


async def current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    digest = hashlib.sha256(token.encode()).hexdigest()
    result = await db.execute(
        select(User).join(UserSession, UserSession.user_id == User.id)
        .where(UserSession.token_hash == digest, UserSession.expires_at > func.now())
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin:
        expected = f"{request.headers.get('x-forwarded-proto', request.url.scheme)}://{request.headers.get('host', '')}"
        if origin != expected:
            raise HTTPException(status_code=403, detail="Invalid origin")


@router.post("/api/auth/register", status_code=201)
async def register(body: Credentials, request: Request, response: Response, db: Annotated[AsyncSession, Depends(get_db)]):
    check_origin(request)
    email = normalized_email(body.email)
    user = User(email=email, password_hash=hash_password(body.password))
    try:
        db.add(user)
        await db.flush()
        return await issue_session(db, response, user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered")


@router.post("/api/auth/login")
async def login(body: Credentials, request: Request, response: Response, db: Annotated[AsyncSession, Depends(get_db)]):
    check_origin(request)
    email = normalized_email(body.email)
    user = (await db.execute(select(User).where(func.lower(User.email) == email))).scalar_one_or_none()
    if user is None or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return await issue_session(db, response, user)


@router.get("/api/auth/me")
async def me(user: Annotated[User, Depends(current_user)]):
    return user_view(user)


@router.post("/api/auth/logout")
async def logout(request: Request, response: Response, db: Annotated[AsyncSession, Depends(get_db)]):
    check_origin(request)
    token = request.cookies.get(COOKIE_NAME)
    if token:
        session = (await db.execute(select(UserSession).where(UserSession.token_hash == hashlib.sha256(token.encode()).hexdigest()))).scalar_one_or_none()
        if session:
            await db.delete(session)
            await db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"status": "ok"}
