import hashlib
from datetime import datetime, timezone

import numpy as np
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Task


def embed_text(text: str, dimension: int | None = None) -> list[float]:
    """Детерминированный stub-эмбеддинг для dev (замените на вызов модели в prod)."""
    dim = dimension or settings.embedding_dimension
    digest = hashlib.sha512(text.encode("utf-8")).digest()
    rng = np.random.default_rng(int.from_bytes(digest[:8], "big"))
    vec = rng.standard_normal(dim).astype(np.float32)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()


def vector_to_pg(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


async def compute_and_store_task_embedding(session: AsyncSession, task_id) -> None:
    result = await session.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        return
    text = f"{task.title}\n{task.statement}"
    vec = embed_text(text)
    now = datetime.now(timezone.utc)
    await session.execute(
        update(Task)
        .where(Task.id == task_id)
        .values(
            embedding=vec,
            embedding_model=settings.embedding_model,
            embedding_model_version=settings.embedding_model_version,
            embedding_updated_at=now,
        )
    )
    await session.commit()
