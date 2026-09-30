from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.db import engine
from app.routers import catalog, communities, olympiads


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    yield
    await engine.dispose()


app = FastAPI(title="Gazprompt Olympiads API", version="1.0.0", lifespan=lifespan,
    docs_url="/olymp-docs",
    openapi_url="/olymp-openapi.json",
    redoc_url="/olymp-redoc",)

app.include_router(catalog.router)
app.include_router(olympiads.router)
app.include_router(communities.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
