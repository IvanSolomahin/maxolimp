from contextlib import asynccontextmanager
from typing import Annotated

import os

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import InitDataPayload, check_origin, issue_session, router as auth_router, verify_init_data
from .db import engine, get_db
from .models import User
from app.routers import admin, olympiads, progress, solution_methods, tasks, topics

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


app = FastAPI(title="Gazprompt Tasks API", version="1.0.0", lifespan=lifespan)
webhook.setup(app, path="/webhook")

app.include_router(tasks.router)
app.include_router(topics.router)
app.include_router(olympiads.router)
app.include_router(solution_methods.router)
app.include_router(admin.router)
app.include_router(auth_router)
app.include_router(progress.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------- Отправка через API MAX ----------

async def send_open_app_button(user_id: int, text: str = "Привет! Нажми кнопку ниже, чтобы открыть мини-приложение."):
    """Отправляет сообщение пользователю с кнопкой open_app."""
    if not user_id:
        return
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(
            f"{MAX_API}/messages",
            params={"user_id": user_id},
            headers={"Authorization": BOT_TOKEN},
            json={
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
                                        "web_app": "t92_hakaton_max_bot",
                                    }
                                ]
                            ]
                        },
                    }
                ],
            },
        )


async def send_user_ans(user_id: int, text: str = "Привет! Напиши /start или 'начать' чтобы получить кнопку запуска приложения еще раз"):
    """Отправляет сообщение пользователю"""
    if not user_id:
        return
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(
            f"{MAX_API}/messages",
            params={"user_id": user_id},
            headers={"Authorization": BOT_TOKEN},
            json={
                "text": text
            },
        )


# ---------- Хендлеры ----------

@dp.message_created()
async def on_message(event: MessageCreated):
    """На /start отправляем приветствие с кнопкой в личку отправителю."""
    text_value = (event.message.body.text or "").strip().lower()
    if text_value in ("/start", "start", "начать"):
        # В личных диалогах MAX адресует по user_id отправителя
        user_id = event.message.sender.user_id
        await send_open_app_button(user_id)
    else:
        user_id = event.message.sender.user_id
        await send_user_ans(user_id)



@app.post("/api/max/validate")
async def validate_init_data(
    payload: InitDataPayload,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
    response: Response,
):
    check_origin(request)
    user = verify_init_data(payload.initData, BOT_TOKEN)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid initData")

    max_id = user["id"]
    statement = insert(User).values(
        max_id=max_id, first_name=user.get("first_name"), username=user.get("username")
    ).on_conflict_do_update(
        index_elements=["max_id"],
        set_={"first_name": user.get("first_name"), "username": user.get("username"), "updated_at": func.now()},
    ).returning(User.id)
    account_id = (await db.execute(statement)).scalar_one()
    account = await db.get(User, account_id)
    view = await issue_session(db, response, account)
    return {"valid": True, "max_id": max_id, "user": view}