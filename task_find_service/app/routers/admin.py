from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models import Task
from app.schemas import StaleEmbeddingItem, StaleEmbeddingsResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/embeddings/stale", response_model=StaleEmbeddingsResponse)
async def stale_embeddings(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_model: str | None = None,
):
    model = current_model or settings.embedding_model
    result = await db.execute(
        select(Task).where(
            or_(
                Task.embedding.is_(None),
                Task.embedding_model.is_(None),
                Task.embedding_model != model,
            )
        )
    )
    tasks = list(result.scalars().all())
    items = [
        StaleEmbeddingItem(
            id=t.id,
            embedding_model=t.embedding_model,
            embedding_updated_at=t.embedding_updated_at,
        )
        for t in tasks
    ]
    return StaleEmbeddingsResponse(count=len(items), items=items)
