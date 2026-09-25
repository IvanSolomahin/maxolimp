from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models import City, Program, ProgramUniversity, Subject, University, UniversityCity
from app.schemas import (
    PaginatedPrograms,
    PaginatedProgramsWithUniversity,
    PaginatedSubjects,
    PaginatedUniversities,
    ProgramItem,
    ProgramWithUniversityItem,
    SubjectRef,
    UniversityListItem,
)

router = APIRouter()


@router.get("/universities", response_model=PaginatedUniversities, tags=["universities"])
async def list_universities(
    db: Annotated[AsyncSession, Depends(get_db)],
    q: str | None = None,
    city_id: int | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    stmt = (
        select(University)
        .options(selectinload(University.cities).selectinload(UniversityCity.city))
        .order_by(University.name)
    )
    if q:
        pattern = f"%{q}%"
        city_match = exists(
            select(1)
            .select_from(UniversityCity)
            .join(City, City.id == UniversityCity.city_id)
            .where(
                UniversityCity.university_id == University.id,
                City.name.ilike(pattern),
            )
        )
        stmt = stmt.where(or_(University.name.ilike(pattern), city_match))
    if city_id is not None:
        stmt = stmt.where(
            exists(
                select(1)
                .select_from(UniversityCity)
                .where(
                    UniversityCity.university_id == University.id,
                    UniversityCity.city_id == city_id,
                )
            )
        )
    count_q = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = int((await db.execute(count_q)).scalar_one())
    rows = list(
        (await db.execute(stmt.limit(size).offset((page - 1) * size))).scalars().all()
    )
    items = [
        UniversityListItem(
            id=u.id,
            name=u.name,
            cities=[link.city.name for link in u.cities],
        )
        for u in rows
    ]
    return PaginatedUniversities(total=total, page=page, size=size, items=items)


@router.get(
    "/universities/{university_id}/programs",
    response_model=PaginatedPrograms,
    tags=["universities"],
)
async def list_university_programs(
    university_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    q: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    stmt = (
        select(Program)
        .join(ProgramUniversity, ProgramUniversity.program_id == Program.id)
        .where(ProgramUniversity.university_id == university_id)
        .order_by(Program.name)
    )
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(Program.name.ilike(pattern), Program.code.ilike(pattern)))

    count_q = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = int((await db.execute(count_q)).scalar_one())
    rows = list(
        (await db.execute(stmt.limit(size).offset((page - 1) * size))).scalars().all()
    )
    return PaginatedPrograms(
        total=total,
        page=page,
        size=size,
        items=[ProgramItem(id=p.id, name=p.name, code=p.code) for p in rows],
    )


@router.get("/programs", response_model=PaginatedProgramsWithUniversity, tags=["programs"])
async def list_programs(
    db: Annotated[AsyncSession, Depends(get_db)],
    q: str | None = None,
    university_id: int | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    stmt = (
        select(Program, ProgramUniversity.university_id)
        .join(ProgramUniversity, ProgramUniversity.program_id == Program.id)
        .order_by(Program.name, ProgramUniversity.university_id)
    )
    if university_id is not None:
        stmt = stmt.where(ProgramUniversity.university_id == university_id)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(Program.name.ilike(pattern), Program.code.ilike(pattern)))

    count_q = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = int((await db.execute(count_q)).scalar_one())
    rows = (await db.execute(stmt.limit(size).offset((page - 1) * size))).all()
    items = [
        ProgramWithUniversityItem(
            id=program.id,
            name=program.name,
            code=program.code,
            university_id=uid,
        )
        for program, uid in rows
    ]
    return PaginatedProgramsWithUniversity(total=total, page=page, size=size, items=items)


@router.get("/subjects", response_model=PaginatedSubjects, tags=["subjects"])
async def list_subjects(
    db: Annotated[AsyncSession, Depends(get_db)],
    q: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    stmt = select(Subject).order_by(Subject.name)
    if q:
        stmt = stmt.where(Subject.name.ilike(f"%{q}%"))
    count_q = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = int((await db.execute(count_q)).scalar_one())
    rows = list(
        (await db.execute(stmt.limit(size).offset((page - 1) * size))).scalars().all()
    )
    return PaginatedSubjects(
        total=total,
        page=page,
        size=size,
        items=[SubjectRef(id=s.id, name=s.name) for s in rows],
    )
