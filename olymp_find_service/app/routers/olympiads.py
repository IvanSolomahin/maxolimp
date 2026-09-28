from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.deps import normalize_benefit_type, public_benefit_type
from app.models import Benefit, Olympiad, Stage, SubjectOlympiad
from app.schemas import (
    BenefitItem,
    BenefitsResponse,
    BenefitTypeRef,
    HostUniversityRef,
    OlympiadDetail,
    PaginatedRecommendations,
    RecommendationItem,
    StageItem,
    StagesResponse,
    SubjectRef,
)

router = APIRouter(tags=["olympiads"])


@router.get("/olympiads/recommendations", response_model=PaginatedRecommendations)
async def recommend_olympiads(
    db: Annotated[AsyncSession, Depends(get_db)],
    university_id: int | None = None,
    program_id: int | None = None,
    benefit_type: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sort: str = Query("complexity", pattern="^(complexity|name)$"),
):
    stored_benefit = normalize_benefit_type(benefit_type)
    stmt = (
        select(SubjectOlympiad)
        .join(Olympiad, Olympiad.id == SubjectOlympiad.olympiad_id)
        .join(Benefit, Benefit.olympiad_id == Olympiad.id)
        .options(
            selectinload(SubjectOlympiad.olympiad).selectinload(Olympiad.benefits),
        )
    )
    if university_id is not None:
        stmt = stmt.where(Benefit.university_id == university_id)
    if program_id is not None:
        stmt = stmt.where(Benefit.program_id == program_id)
    if stored_benefit is not None:
        stmt = stmt.where(Benefit.benefit_type == stored_benefit)

    links = list((await db.execute(stmt.distinct())).scalars().unique().all())

    grouped: dict[int, RecommendationItem] = {}
    for subj_link in sorted(links, key=lambda link: link.id):
        olympiad = subj_link.olympiad
        if olympiad.id in grouped:
            continue
        matched_benefits = olympiad.benefits
        if university_id is not None:
            matched_benefits = [b for b in matched_benefits if b.university_id == university_id]
        if program_id is not None:
            matched_benefits = [b for b in matched_benefits if b.program_id == program_id]
        if stored_benefit is not None:
            matched_benefits = [b for b in matched_benefits if b.benefit_type == stored_benefit]
        if not matched_benefits:
            continue
        benefit = matched_benefits[0]
        shown_type = (
            public_benefit_type(benefit.benefit_type)
            if benefit_type and benefit_type.strip().lower() == "bvi"
            else benefit.benefit_type
        )
        grouped[olympiad.id] = RecommendationItem(
            id=subj_link.id,
            name=olympiad.name,
            complexity=olympiad.complexity,
            benefit=BenefitTypeRef(type=shown_type),
        )

    items_raw = list(grouped.values())
    if sort == "name":
        items_raw.sort(key=lambda x: x.name)
    else:
        items_raw.sort(key=lambda x: (-(x.complexity or 0), x.name))

    total = len(items_raw)
    offset = (page - 1) * size
    return PaginatedRecommendations(
        total=total,
        page=page,
        size=size,
        items=items_raw[offset : offset + size],
    )


@router.get("/olympiads/{olympiad_id}", response_model=OlympiadDetail)
async def get_olympiad(olympiad_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(SubjectOlympiad)
        .where(SubjectOlympiad.id == olympiad_id)
        .options(
            selectinload(SubjectOlympiad.subject),
            selectinload(SubjectOlympiad.olympiad).selectinload(Olympiad.host_university),
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="Olympiad not found")
    olympiad = link.olympiad
    return OlympiadDetail(
        id=link.id,
        name=olympiad.name,
        complexity=olympiad.complexity,
        description=olympiad.description,
        host_university=HostUniversityRef(
            id=olympiad.host_university.id,
            name=olympiad.host_university.name,
        ) if olympiad.host_university else None,
        subjects=[SubjectRef(id=link.subject.id, name=link.subject.name)],
    )


@router.get("/olympiads/{olympiad_id}/stages", response_model=StagesResponse)
async def get_olympiad_stages(
    olympiad_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    link = await db.get(SubjectOlympiad, olympiad_id)
    if link is None:
        raise HTTPException(status_code=404, detail="Olympiad not found")
    result = await db.execute(
        select(Stage).where(Stage.olymp_id == link.olympiad_id).order_by(Stage.start_date)
    )
    items = [
        StageItem(
            id=s.stage_id,
            name=s.name,
            is_online=s.is_online,
            location=s.location,
            start_date=s.start_date,
            end_date=s.end_date,
        )
        for s in result.scalars().all()
    ]
    return StagesResponse(items=items)


@router.get("/olympiads/{olympiad_id}/benefits", response_model=BenefitsResponse)
async def get_olympiad_benefits(
    olympiad_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    university_id: int | None = None,
    program_id: int | None = None,
):
    link = await db.get(SubjectOlympiad, olympiad_id)
    if link is None:
        raise HTTPException(status_code=404, detail="Olympiad not found")
    stmt = select(Benefit).where(Benefit.olympiad_id == link.olympiad_id)
    if university_id is not None:
        stmt = stmt.where(Benefit.university_id == university_id)
    if program_id is not None:
        stmt = stmt.where(Benefit.program_id == program_id)
    result = await db.execute(stmt.order_by(Benefit.id))
    items = [
        BenefitItem(
            id=b.id,
            university_id=b.university_id,
            program_id=b.program_id,
            benefit_type=b.benefit_type,
        )
        for b in result.scalars().all()
    ]
    return BenefitsResponse(items=items)
