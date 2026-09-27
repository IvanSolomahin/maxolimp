from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from pydantic import BaseModel

from .db import engine
from app.routers import admin, olympiads, solution_methods, tasks, topics

import os
import hmac
import hashlib
import json
import time
from urllib.parse import parse_qsl

from maxapi import Bot, Dispatcher
from maxapi.webhook.fastapi import FastAPIMaxWebhook
from maxapi.types import BotStarted, MessageCreated


BOT_TOKEN = os.getenv("MAX_BOT_TOKEN")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://gazprompt.duckdns.org")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# Webhook-объект нужен ДО FastAPI, чтобы передать его lifespan
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

# MAX webhook-роут (/webhook)
webhook.setup(app, path="/webhook")

app.include_router(tasks.router)
app.include_router(topics.router)
app.include_router(olympiads.router)
app.include_router(solution_methods.router)
app.include_router(admin.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------- Хендлеры MAX-бота ----------

@dp.bot_started()
async def on_bot_started(event: BotStarted):
    await event.bot.send_message(
        chat_id=event.chat_id,
        text="Привет! Нажми кнопку ниже, чтобы открыть мини-приложение.",
        attachments=[
            {
                "type": "inline_keyboard",
                "payload": {
                    "buttons": [
                        [
                            {
                                "type": "open_app",
                                "web_app": FRONTEND_URL,
                            }
                        ]
                    ]
                },
            }
        ],
    )


@dp.message_created()
async def on_message(event: MessageCreated):
    if event.message.body.text == "/start":
        await event.message.answer("Привет! Кнопка для открытия приложения выше.")


# ---------- Валидация initData от мини-приложения ----------

class InitDataPayload(BaseModel):
    initData: str


def verify_init_data(init_data: str, bot_token: str) -> dict | None:
    """Проверка подписи initData от MAX WebApp (HMAC-SHA256)."""
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


from .db import get_db
from typing import Annotated
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

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