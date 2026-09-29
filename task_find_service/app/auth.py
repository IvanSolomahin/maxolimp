import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated
from urllib.parse import parse_qsl

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import User, UserSession

router = APIRouter(tags=["auth"])
COOKIE_NAME = "maxolimp_session"
SESSION_SECONDS = 30 * 24 * 60 * 60


class InitDataPayload(BaseModel):
    initData: str


def verify_init_data(init_data: str, bot_token: str | None) -> dict | None:
    if not init_data or not bot_token:
        return None
    try:
        # MAX Bridge exposes the signed WebAppData value as initData. Some
        # launch contexts expose the complete URL fragment instead, where the
        # same value is wrapped in WebAppData alongside platform metadata.
        outer_pairs = parse_qsl(init_data.lstrip("#"), keep_blank_values=True, strict_parsing=True)
        outer = dict(outer_pairs)
        if len(outer) != len(outer_pairs):
            return None
        if "WebAppData" in outer:
            init_data = outer["WebAppData"]

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


def user_view(user: User) -> dict:
    return {"id": user.id, "max_id": user.max_id, "first_name": user.first_name}


def mark_cookie_partitioned(response: Response) -> None:
    """Add CHIPS' Partitioned attribute to our session cookie."""
    cookie_prefix = f"{COOKIE_NAME}=".encode()
    for index in range(len(response.raw_headers) - 1, -1, -1):
        name, value = response.raw_headers[index]
        if name.lower() == b"set-cookie" and value.startswith(cookie_prefix):
            if b"; partitioned" not in value.lower():
                response.raw_headers[index] = (name, value + b"; Partitioned")
            return


async def issue_session(db: AsyncSession, response: Response, user: User) -> dict:
    token = secrets.token_urlsafe(32)
    await db.execute(delete(UserSession).where(UserSession.expires_at <= func.now()))
    db.add(UserSession(
        user_id=user.id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=SESSION_SECONDS),
    ))
    await db.commit()
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_SECONDS, httponly=True, secure=True, samesite="none", path="/")
    mark_cookie_partitioned(response)
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
    if user is None or user.max_id is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin:
        expected = f"{request.headers.get('x-forwarded-proto', request.url.scheme)}://{request.headers.get('host', '')}"
        if origin != expected:
            raise HTTPException(status_code=403, detail="Invalid origin")


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
    response.delete_cookie(COOKIE_NAME, path="/", secure=True, httponly=True, samesite="none")
    mark_cookie_partitioned(response)
    return {"status": "ok"}
