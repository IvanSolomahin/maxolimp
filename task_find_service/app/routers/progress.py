import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import check_origin, current_user
from app.db import get_db
from app.models import Olympiad, SolvedTask, Task, User

router = APIRouter(prefix="/progress", tags=["progress"])
MOSCOW = ZoneInfo("Europe/Moscow")
Period = Literal["week", "month", "year"]


def period_bounds(period: Period, now: datetime | None = None) -> tuple[datetime, datetime, list[tuple[datetime, datetime]]]:
    today = (now or datetime.now(timezone.utc)).astimezone(MOSCOW).date()
    if period == "year":
        buckets = []
        month_number = today.year * 12 + today.month - 1
        for offset in range(-11, 1):
            first = month_number + offset
            start = datetime(first // 12, first % 12 + 1, 1, tzinfo=MOSCOW)
            next_month = first + 1
            end = datetime(next_month // 12, next_month % 12 + 1, 1, tzinfo=MOSCOW)
            buckets.append((start, end))
    else:
        length = 7 if period == "week" else 30
        buckets = []
        for offset in range(length - 1, -1, -1):
            day = today - timedelta(days=offset)
            start = datetime(day.year, day.month, day.day, tzinfo=MOSCOW)
            buckets.append((start, start + timedelta(days=1)))
    return buckets[0][0], buckets[-1][1], buckets


def filtered_query(user_id: int, olympiad_id: uuid.UUID | None, tag: str | None):
    query = select(SolvedTask, Task).join(Task, Task.id == SolvedTask.task_id).where(SolvedTask.user_id == user_id)
    if olympiad_id is not None:
        query = query.where(Task.olympiad_id == olympiad_id)
    if tag is not None:
        query = query.where(Task.classifier == tag)
    return query


@router.get("/tasks/{task_id}")
async def task_progress(task_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(current_user)]):
    task = await db.get(Task, task_id)
    if task is None or task.status != "published":
        raise HTTPException(status_code=404, detail="Task not found")
    solved = await db.get(SolvedTask, (user.id, task_id))
    return {"solved": solved is not None, "solved_at": solved.solved_at if solved else None}


@router.post("/tasks/{task_id}/solved")
async def mark_solved(task_id: uuid.UUID, request: Request, db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(current_user)]):
    check_origin(request)
    task = await db.get(Task, task_id)
    if task is None or task.status != "published":
        raise HTTPException(status_code=404, detail="Task not found")
    statement = insert(SolvedTask).values(user_id=user.id, task_id=task_id).on_conflict_do_nothing(index_elements=["user_id", "task_id"])
    await db.execute(statement)
    await db.commit()
    solved = await db.get(SolvedTask, (user.id, task_id))
    return {"solved": True, "solved_at": solved.solved_at}


@router.get("/solved")
async def list_solved(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    period: Period | None = None,
    olympiad_id: uuid.UUID | None = None,
    tag: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    query = filtered_query(user.id, olympiad_id, tag)
    if period:
        start, end, _ = period_bounds(period)
        query = query.where(SolvedTask.solved_at >= start, SolvedTask.solved_at < end)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await db.execute(
        query.outerjoin(Olympiad, Task.olympiad_id == Olympiad.id)
        .add_columns(Olympiad.name)
        .order_by(SolvedTask.solved_at.desc(), Task.id)
        .limit(size).offset((page - 1) * size)
    )).all()
    return {
        "total": total, "page": page, "size": size,
        "items": [
            {"id": task.id, "title": task.title or task.classifier or task.statement[:100],
             "olympiad_id": task.olympiad_id, "olympiad": olympiad_name,
             "tag": task.classifier, "solved_at": solved.solved_at}
            for solved, task, olympiad_name in rows
        ],
    }


@router.get("/statistics")
async def statistics(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    period: Period = "week",
    olympiad_id: uuid.UUID | None = None,
    tag: str | None = None,
):
    start, end, ranges = period_bounds(period)
    base = filtered_query(user.id, olympiad_id, tag)
    rows = (await db.execute(
        base.outerjoin(Olympiad, Task.olympiad_id == Olympiad.id)
        .add_columns(Olympiad.name)
    )).all()
    period_rows = [(solved, task, name) for solved, task, name in rows if start <= solved.solved_at < end]
    values = []
    for bucket_start, bucket_end in ranges:
        values.append({"from": bucket_start.isoformat(), "to": bucket_end.isoformat(),
                       "count": sum(bucket_start <= solved.solved_at < bucket_end for solved, _, _ in period_rows)})
    olympiads: dict[tuple[uuid.UUID | None, str | None], int] = {}
    tags: dict[str | None, int] = {}
    for _, task, name in period_rows:
        key = (task.olympiad_id, name)
        olympiads[key] = olympiads.get(key, 0) + 1
        tags[task.classifier] = tags.get(task.classifier, 0) + 1
    active_days = len({solved.solved_at.astimezone(MOSCOW).date() for solved, _, _ in period_rows})
    return {
        "period": period, "from": start.isoformat(), "to": end.isoformat(),
        "total_period": len(period_rows), "total_all_time": len(rows), "active_days": active_days,
        "buckets": values,
        "by_olympiad": [
            {"id": oid, "name": name or "Без олимпиады", "count": count}
            for (oid, name), count in sorted(olympiads.items(), key=lambda item: -item[1])
        ],
        "by_tag": [
            {"tag": name, "name": name or "Без тега", "count": count}
            for name, count in sorted(tags.items(), key=lambda item: -item[1])
        ],
    }
