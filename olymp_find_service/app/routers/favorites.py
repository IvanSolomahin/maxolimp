from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.deps import current_user_id
from app.models import Favorite, Olympiad
from app.schemas import (
    AddFavoriteRequest,
    FavoriteItem,
    FavoriteMutationResponse,
    PaginatedFavorites,
)

router = APIRouter(tags=["favorites"])


@router.get("/favorites", response_model=PaginatedFavorites)
async def list_favorites(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[int, Depends(current_user_id)],
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    base = (
        select(Favorite)
        .where(Favorite.user_id == user_id)
        .options(
            selectinload(Favorite.olympiad).selectinload(SubjectOlympiad.subject),
            selectinload(Favorite.olympiad).selectinload(SubjectOlympiad.olympiad).selectinload(Olympiad.benefits),
        )
        .order_by(Favorite.created_at.desc())
    )
    count_q = select(func.count()).select_from(
        select(Favorite).where(Favorite.user_id == user_id).subquery()
    )
    total = int((await db.execute(count_q)).scalar_one())
    rows = list(
        (await db.execute(base.limit(size).offset((page - 1) * size))).scalars().all()
    )
    items = []
    for fav in rows:
        link = fav.olympiad
        olympiad = link.olympiad
        subject_name = link.subject.name
        benefit_type = olympiad.benefits[0].benefit_type if olympiad.benefits else None
        items.append(
            FavoriteItem(
                olympiad_id=link.id,
                name=olympiad.name,
                complexity=olympiad.complexity,
                benefit_type=benefit_type,
            )
        )
    return PaginatedFavorites(total=total, page=page, size=size, items=items)


@router.post("/favorites", response_model=FavoriteMutationResponse)
async def add_favorite(
    body: AddFavoriteRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[int, Depends(current_user_id)],
):
    olympiad = await db.get(SubjectOlympiad, body.olympiad_id)
    if olympiad is None:
        raise HTTPException(status_code=404, detail="Olympiad not found")
    existing = await db.get(Favorite, (user_id, body.olympiad_id))
    if existing is None:
        db.add(Favorite(user_id=user_id, olympiad_id=body.olympiad_id))
        await db.commit()
    return FavoriteMutationResponse(success=True, olympiad_id=body.olympiad_id)


@router.delete("/favorites/{olympiad_id}", response_model=FavoriteMutationResponse)
async def delete_favorite(
    olympiad_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[int, Depends(current_user_id)],
):
    favorite = await db.get(Favorite, (user_id, olympiad_id))
    if favorite is None:
        raise HTTPException(status_code=404, detail="Favorite not found")
    await db.delete(favorite)
    await db.commit()
    return FavoriteMutationResponse(success=True, olympiad_id=olympiad_id)
