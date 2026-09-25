from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.schemas import StaleEmbeddingItem, StaleEmbeddingsResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/embeddings/stale", response_model=StaleEmbeddingsResponse)
async def stale_embeddings(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_model: str | None = None,
):
    model = current_model or settings.embedding_model
    result = await db.execute(text("""
        SELECT t.id, e.model AS embedding_model, e.updated_at AS embedding_updated_at
        FROM tasks t LEFT JOIN task_embeddings e
          ON e.task_id = t.id AND e.kind = 'topic' AND e.model = :model
        WHERE e.task_id IS NULL
    """), {"model": model})
    tasks = result.mappings().all()
    items = [
        StaleEmbeddingItem(
            id=t["id"],
            embedding_model=t["embedding_model"],
            embedding_updated_at=t["embedding_updated_at"],
        )
        for t in tasks
    ]
    return StaleEmbeddingsResponse(count=len(items), items=items)
