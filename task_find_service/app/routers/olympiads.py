import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Olympiad
from app.schemas import (
    CreateEntityResponse,
    CreateOlympiadRequest,
    OlympiadRef,
    OlympiadsResponse,
    StatusOk,
    UpdateOlympiadRequest,
)

router = APIRouter(tags=["olympiads"])


@router.get("/olympiads", response_model=OlympiadsResponse)
async def list_olympiads(
    db: Annotated[AsyncSession, Depends(get_db)],
    q: str | None = None,
):
    stmt = select(Olympiad).order_by(Olympiad.name)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(Olympiad.name.ilike(pattern) | Olympiad.short_name.ilike(pattern))
    result = await db.execute(stmt)
    items = [
        OlympiadRef(id=o.id, name=o.name, short_name=o.short_name)
        for o in result.scalars().all()
    ]
    return OlympiadsResponse(items=items)


@router.post("/olympiads", response_model=CreateEntityResponse)
async def create_olympiad(
    body: CreateOlympiadRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    olympiad = Olympiad(name=body.name, short_name=body.short_name)
    db.add(olympiad)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Olympiad with this name already exists") from exc
    await db.refresh(olympiad)
    return CreateEntityResponse(id=olympiad.id)


@router.patch("/olympiads/{olympiad_id}", response_model=OlympiadRef)
async def update_olympiad(
    olympiad_id: uuid.UUID,
    body: UpdateOlympiadRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    olympiad = await db.get(Olympiad, olympiad_id)
    if olympiad is None:
        raise HTTPException(status_code=404, detail="Olympiad not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(olympiad, field, value)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Olympiad with this name already exists") from exc
    await db.refresh(olympiad)
    return OlympiadRef(id=olympiad.id, name=olympiad.name, short_name=olympiad.short_name)


@router.delete("/olympiads/{olympiad_id}", response_model=StatusOk)
async def delete_olympiad(
    olympiad_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    olympiad = await db.get(Olympiad, olympiad_id)
    if olympiad is None:
        raise HTTPException(status_code=404, detail="Olympiad not found")
    await db.delete(olympiad)
    await db.commit()
    return StatusOk()
