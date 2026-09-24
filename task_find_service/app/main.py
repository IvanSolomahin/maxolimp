from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.db import engine
from app.routers import admin, olympiads, solution_methods, tasks, topics


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    yield
    await engine.dispose()


app = FastAPI(title="Gazprompt Tasks API", version="1.0.0", lifespan=lifespan)

app.include_router(tasks.router)
app.include_router(topics.router)
app.include_router(olympiads.router)
app.include_router(solution_methods.router)
app.include_router(admin.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
