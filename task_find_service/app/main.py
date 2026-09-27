from contextlib import asynccontextmanager
from typing import Annotated

import hashlib
import hmac
import json
import os
import time
from urllib.parse import parse_qsl

import httpx
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .db import engine, get_db
from app.routers import admin, olympiads, solution_methods, tasks, topics

from maxapi import Bot, Dispatcher
from maxapi.types import MessageCreated
from maxapi.webhook.fastapi import FastAPIMaxWebhook


BOT_TOKEN = os.getenv("MAX_BOT_TOKEN")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://gazprompt.duckdns.org")
MAX_API = "https://platform-api2.max.ru"


bot = Bot(BOT_TOKEN)
dp = Dispatcher()

webhook = FastAPIMaxWebhook(dp=dp, bot=bot)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    async with webhook.lifespan(app):
        yield
    await engine.dispose()


app = FastAPI(
    title="Gazprompt Tasks API",
    version="1.0.0",
    lifespan=lifespan,
)

webhook.setup(app, path="/webhook")

app.include_router(tasks.router)
app.include_router(topics.router)
app.include_router(olympiads.router)
app.include_router(solution_methods.router)
app.include_router(admin.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------- Отправка через чистый API MAX ----------

async def send_open_app_button(chat_id: int, text: str = "Привет! Нажми кнопку ниже, чтобы открыть мини-приложение."):
    """Отправляет сообщение с кнопкой open_app напрямую через API MAX."""
    if not chat_id:
        return
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(
            f"{MAX_API}/messages",
            params={"access_token": BOT_TOKEN},
            json={
                "chat_id": chat_id,
                "text": text,
                "attachments": [
                    {
                        "type": "inline_keyboard",
                        "payload": {
                            "buttons": [
                                [
                                    {
                                        "type": "open_app",
                                        "text": "Открыть приложение",
                                        "web_app": FRONTEND_URL,
                                    }
                                ]
                            ]
                        },
                    }
                ],
            },
        )


# ---------- Хендлеры ----------

@dp.message_created()
async def on_message(event: MessageCreated):
    """На любое сообщение /start отправляем приветствие с кнопкой."""
    text_value = (event.message.body.text or "").strip().lower()
    if text_value in ("/start", "start", "начать"):
        chat_id = event.message.recipient.chat_id
        await send_open_app_button(chat_id)


# ---------- Валидация initData ----------

class InitDataPayload(BaseModel):
    initData: str


def verify_init_data(init_data: str, bot_token: str) -> dict | None:
    if not init_data or not bot_token:
        return None
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        return None

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed, received_hash):
        return None

    try:
        auth_date = int(parsed.get("auth_date", "0"))
    except ValueError:
        return None
    if time.time() - auth_date > 3600:
        return None

    try:
        return json.loads(parsed.get("user", "{}"))
    except json.JSONDecodeError:
        return None


@app.post("/api/max/validate")
async def validate_init_data(
    payload: InitDataPayload,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    user = verify_init_data(payload.initData, BOT_TOKEN)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid initData")

    max_id = user.get("id")

    await db.execute(
        text("""
            INSERT INTO users (max_id, first_name, username)
            VALUES (:max_id, :first_name, :username)
            ON CONFLICT (max_id) DO UPDATE
            SET first_name = EXCLUDED.first_name,
                username   = EXCLUDED.username,
                updated_at = NOW()
        """),
        {
            "max_id": max_id,
            "first_name": user.get("first_name"),
            "username": user.get("username"),
        },
    )
    await db.commit()

    return {"valid": True, "max_id": max_id, "user": user}