import hashlib
import math
import uuid

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Task


def topic_text(task: Task) -> str:
    return "\n".join(part for part in ((task.classifier or "").strip(), task.statement.strip()) if part)


def vector_to_pg(vec: list[float]) -> str:
    return "[" + ",".join(str(x) for x in vec) + "]"


async def embed_text(value: str) -> list[float]:
    if not settings.aitunnel_api_key:
        raise RuntimeError("AITUNNEL_API_KEY не задан")
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            "https://api.aitunnel.ru/v1/embeddings",
            headers={"Authorization": f"Bearer {settings.aitunnel_api_key}"},
            json={"model": settings.embedding_model, "input": [value]},
        )
        response.raise_for_status()
    data = response.json()["data"]
    if len(data) != 1 or data[0].get("index") != 0:
        raise ValueError("Неверный ответ сервиса эмбеддингов")
    vector = data[0]["embedding"]
    if len(vector) != settings.embedding_dimension or any(not math.isfinite(x) for x in vector):
        raise ValueError("Неверная размерность или значения эмбеддинга")
    return vector


async def compute_and_store_task_embedding(session: AsyncSession, task_id: uuid.UUID) -> None:
    task = await session.get(Task, task_id)
    if task is None:
        return
    result = await session.execute(
        text("SELECT content FROM solutions WHERE task_id = :id AND NOT is_generated ORDER BY created_at LIMIT 1"),
        {"id": task_id},
    )
    solution = result.scalar_one_or_none() or ""
    for kind, value in (("topic", topic_text(task)), ("solution", solution)):
        params = {"id": task_id, "kind": kind, "model": settings.embedding_model,
                  "dimensions": settings.embedding_dimension}
        if not value:
            await session.execute(text("DELETE FROM task_embeddings WHERE task_id = :id AND kind = :kind AND model = :model"), params)
            continue
        content_hash = hashlib.sha256(value.encode()).hexdigest()
        existing = await session.execute(text("SELECT text_hash FROM task_embeddings WHERE task_id = :id AND kind = :kind AND model = :model AND dimensions = :dimensions"), params)
        if existing.scalar_one_or_none() == content_hash:
            continue
        vector = await embed_text(value)
        await session.execute(text("""
            INSERT INTO task_embeddings (task_id, kind, model, dimensions, text_hash, embedding)
            VALUES (:id, :kind, :model, :dimensions, :hash, CAST(:vector AS vector))
            ON CONFLICT (task_id, kind, model, dimensions) DO UPDATE SET
                text_hash = EXCLUDED.text_hash, embedding = EXCLUDED.embedding, updated_at = now()
        """), {**params, "hash": content_hash, "vector": vector_to_pg(vector)})
    await session.commit()
