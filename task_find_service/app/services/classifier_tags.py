from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ClassifierTag, TaskClassifierTag


def normalize_tags(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def split_source_classifier(value: str | None) -> list[str]:
    # ETL separates tag names with " , "; a comma inside a name is significant.
    return normalize_tags((value or "").split(" , "))


async def replace_task_tags(db: AsyncSession, task_id, values: list[str]) -> None:
    names = normalize_tags(values)
    await db.execute(delete(TaskClassifierTag).where(TaskClassifierTag.task_id == task_id))
    if not names:
        return
    await db.execute(insert(ClassifierTag).values([{"name": name} for name in names]).on_conflict_do_nothing(index_elements=["name"]))
    tags = (await db.execute(select(ClassifierTag).where(ClassifierTag.name.in_(names)))).scalars().all()
    db.add_all(TaskClassifierTag(task_id=task_id, tag_id=tag.id) for tag in tags)
