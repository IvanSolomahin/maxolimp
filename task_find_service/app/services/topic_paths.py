import re
import uuid

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Topic

_UNSET = object()


def path_segment(name: str) -> str:
    seg = name.strip().lower()
    seg = re.sub(r"[^\w\-]+", "-", seg, flags=re.UNICODE)
    seg = re.sub(r"-+", "-", seg).strip("-")
    return seg or "topic"


def depth_from_path(path: str) -> int:
    return max(len(path.split("/")) - 1, 0)


async def resolve_topic_path(
    session: AsyncSession,
    *,
    name: str,
    parent_id: uuid.UUID | None,
) -> tuple[str, int]:
    segment = path_segment(name)
    if parent_id is None:
        return segment, 0
    parent = await session.get(Topic, parent_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Parent topic not found")
    return f"{parent.path}/{segment}", parent.depth + 1


async def is_ancestor(session: AsyncSession, ancestor_id: uuid.UUID, node_id: uuid.UUID) -> bool:
    node = await session.get(Topic, node_id)
    if node is None:
        return False
    ancestor = await session.get(Topic, ancestor_id)
    if ancestor is None:
        return False
    return node.path == ancestor.path or node.path.startswith(f"{ancestor.path}/")


async def repath_subtree(session: AsyncSession, old_path: str, new_path: str) -> None:
    result = await session.execute(
        select(Topic).where(
            or_(Topic.path == old_path, Topic.path.like(f"{old_path}/%"))
        )
    )
    for topic in result.scalars().all():
        if topic.path == old_path:
            topic.path = new_path
        else:
            topic.path = new_path + topic.path[len(old_path) :]
        topic.depth = depth_from_path(topic.path)


async def apply_topic_location(
    session: AsyncSession,
    topic: Topic,
    *,
    name: str | None = None,
    parent_id: uuid.UUID | None | object = _UNSET,
) -> None:
    new_name = name if name is not None else topic.name
    if parent_id is _UNSET:
        new_parent_id = topic.parent_id
    else:
        new_parent_id = parent_id

    if new_parent_id == topic.id:
        raise HTTPException(status_code=400, detail="Topic cannot be its own parent")
    if new_parent_id is not None and await is_ancestor(session, topic.id, new_parent_id):
        raise HTTPException(status_code=400, detail="Cannot move topic under its descendant")

    new_path, new_depth = await resolve_topic_path(
        session, name=new_name, parent_id=new_parent_id
    )
    old_path = topic.path
    topic.name = new_name
    topic.parent_id = new_parent_id
    if new_path != old_path:
        await repath_subtree(session, old_path, new_path)
    else:
        topic.path = new_path
        topic.depth = new_depth
