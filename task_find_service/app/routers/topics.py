import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Topic
from app.schemas import (
    CreateEntityResponse,
    CreateTopicRequest,
    StatusOk,
    TopicRef,
    TopicsResponse,
    UpdateTopicRequest,
)
from app.services.hierarchy import fetch_topics_tree
from app.services.topic_paths import _UNSET, apply_topic_location, resolve_topic_path

router = APIRouter(tags=["topics"])


@router.get("/topics", response_model=TopicsResponse)
async def list_topics(
    db: Annotated[AsyncSession, Depends(get_db)],
    flat: bool = False,
    parent_id: uuid.UUID | None = None,
    depth_max: int | None = None,
):
    items = await fetch_topics_tree(
        db, flat=flat, parent_id=parent_id, depth_max=depth_max
    )
    return TopicsResponse(items=items)


@router.post("/topics", response_model=CreateEntityResponse)
async def create_topic(
    body: CreateTopicRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    path, depth = await resolve_topic_path(
        db, name=body.name, parent_id=body.parent_id
    )
    topic = Topic(
        name=body.name,
        parent_id=body.parent_id,
        path=path,
        depth=depth,
    )
    db.add(topic)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Topic with this name already exists under the same parent",
        ) from exc
    await db.refresh(topic)
    return CreateEntityResponse(id=topic.id)


@router.patch("/topics/{topic_id}", response_model=TopicRef)
async def update_topic(
    topic_id: uuid.UUID,
    body: UpdateTopicRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    topic = await db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    data = body.model_dump(exclude_unset=True)
    if not data:
        return TopicRef(id=topic.id, name=topic.name, path=topic.path)

    await apply_topic_location(
        db,
        topic,
        name=data.get("name"),
        parent_id=data["parent_id"] if "parent_id" in data else _UNSET,
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Topic with this name already exists under the same parent",
        ) from exc
    await db.refresh(topic)
    return TopicRef(id=topic.id, name=topic.name, path=topic.path)


@router.delete("/topics/{topic_id}", response_model=StatusOk)
async def delete_topic(
    topic_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    topic = await db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    children = await db.execute(
        select(func.count()).select_from(Topic).where(Topic.parent_id == topic_id)
    )
    if int(children.scalar_one()) > 0:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete topic with child topics; remove or move children first",
        )

    await db.delete(topic)
    await db.commit()
    return StatusOk()
