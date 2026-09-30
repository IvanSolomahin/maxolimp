import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import SessionLocal, get_db
from app.models import Hint, Solution, Task, TaskTopic, TaskEmbedding
from app.config import settings
from app.schemas import (
    AssignOlympiadsRequest,
    AssignSolutionMethodRequest,
    AssignTopicsRequest,
    CreateTaskRequest,
    CreateTaskResponse,
    GenerateSolutionRequest,
    GenerateSolutionResponse,
    EmbeddingQueuedResponse,
    HintResponse,
    PaginatedTasks,
    SetDifficultyRequest,
    SetDifficultyResponse,
    SimilarTasksResponse,
    SolutionItem,
    SolutionsResponse,
    SourceInfo,
    StatusOk,
    TaskDetail,
    TaskListItem,
    TopicRef,
    OlympiadRef,
    SolutionMethodRef,
    UpdateTaskRequest,
)
from app.services.embeddings import compute_and_store_task_embedding
from app.services.llm import generate_hint, generate_solution, check_solution
from app.services.search import (
    hybrid_search_tasks,
    keyword_search,
    similar_tasks,
    tasks_by_olympiads,
    tasks_by_topics,
    _snippet,
)

router = APIRouter(tags=["tasks"])


def _display_title(task: Task) -> str:
    return task.title or task.classifier or _snippet(task.statement, 100) or "Задача без условия"


def _parse_csv_uuids(value: str | None) -> list[uuid.UUID]:
    if not value:
        return []
    out: list[uuid.UUID] = []
    for part in value.split(","):
        part = part.strip()
        if part:
            out.append(uuid.UUID(part))
    return out


def _method_ref(task: Task) -> SolutionMethodRef | None:
    if not task.solution_method:
        return None
    sm = task.solution_method
    return SolutionMethodRef(id=sm.id, name=sm.name, path=sm.path)


@router.get("/tasks", response_model=PaginatedTasks)
async def list_tasks(
    db: Annotated[AsyncSession, Depends(get_db)],
    q: str | None = None,
    subject: str | None = Query(None, pattern="^(math|physics)$"),
    olympiad_id: uuid.UUID | None = None,
    classifiers: list[str] = Query(default=[]),
    grade: int | None = None,
    mode: str = Query("topic", pattern="^(topic|solution|both)$"),
    difficulty_min: int | None = None,
    difficulty_max: int | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    stage: str | None = None,
    solution_method_id: uuid.UUID | None = None,
    sort: str = Query("relevance", pattern="^(relevance|newest|difficulty)$"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    total, rows = await hybrid_search_tasks(
        db,
        q=q,
        subject=subject,
        olympiad_id=olympiad_id,
        classifiers=classifiers,
        grade=grade,
        mode=mode,
        difficulty_min=difficulty_min,
        difficulty_max=difficulty_max,
        year_from=year_from,
        year_to=year_to,
        stage=stage,
        solution_method_id=solution_method_id,
        sort=sort,
        page=page,
        size=size,
    )
    if not rows:
        return PaginatedTasks(total=total, page=page, size=size, items=[])

    ids = [r["id"] for r in rows]
    tasks_res = await db.execute(
        select(Task)
        .where(Task.id.in_(ids))
        .options(selectinload(Task.solution_method), selectinload(Task.olympiad))
    )
    by_id = {t.id: t for t in tasks_res.scalars().all()}

    items: list[TaskListItem] = []
    for r in rows:
        t = by_id.get(r["id"])
        if not t:
            continue
        items.append(
            TaskListItem(
                id=t.id,
                title=_display_title(t),
                difficulty=t.difficulty,
                solution_method=_method_ref(t),
                snippet=r.get("snippet") or _snippet(t.statement),
                number=t.source_problem_number,
                olympiad=t.olympiad.name if t.olympiad else None,
                olympiad_short_name=t.olympiad.short_name if t.olympiad else None,
                score=float(r["score"]) if r.get("score") is not None else None,
            )
        )
    return PaginatedTasks(total=total, page=page, size=size, items=items)


@router.get("/tasks/classifiers")
async def list_classifiers(
    db: Annotated[AsyncSession, Depends(get_db)],
    subject: str = Query(..., pattern="^(math|physics)$"),
):
    result = await db.execute(
        select(Task.classifier)
        .where(
            Task.subject == subject,
            Task.status == "published",
            Task.classifier.is_not(None),
            func.btrim(Task.classifier) != "",
        )
        .distinct()
        .order_by(Task.classifier)
    )
    return {"items": list(result.scalars().all())}


@router.get("/tasks/by-topics", response_model=PaginatedTasks)
async def list_tasks_by_topics(
    db: Annotated[AsyncSession, Depends(get_db)],
    topic_ids: str = Query(..., description="CSV UUID"),
    include_subtopics: bool = False,
    match: str = Query("any", pattern="^(any|all)$"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    ids = _parse_csv_uuids(topic_ids)
    total, tasks = await tasks_by_topics(
        db,
        topic_ids=ids,
        include_subtopics=include_subtopics,
        match=match,
        page=page,
        size=size,
    )
    items = [
        TaskListItem(
            id=t.id,
            title=_display_title(t),
            difficulty=t.difficulty,
            solution_method=_method_ref(t),
        )
        for t in tasks
    ]
    return PaginatedTasks(total=total, page=page, size=size, items=items)


@router.get("/tasks/by-olympiads", response_model=PaginatedTasks)
async def list_tasks_by_olympiads(
    db: Annotated[AsyncSession, Depends(get_db)],
    olympiad_ids: str = Query(..., description="CSV UUID"),
    year_from: int | None = None,
    year_to: int | None = None,
    stage: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    ids = _parse_csv_uuids(olympiad_ids)
    total, tasks = await tasks_by_olympiads(
        db,
        olympiad_ids=ids,
        year_from=year_from,
        year_to=year_to,
        stage=stage,
        page=page,
        size=size,
    )
    items = [
        TaskListItem(
            id=t.id,
            title=_display_title(t),
            difficulty=t.difficulty,
            solution_method=_method_ref(t),
        )
        for t in tasks
    ]
    return PaginatedTasks(total=total, page=page, size=size, items=items)


@router.get("/tasks/search-by-keywords", response_model=PaginatedTasks)
async def search_by_keywords(
    db: Annotated[AsyncSession, Depends(get_db)],
    keywords: str = Query(..., description="слова через запятую"),
    mode: str = Query("and", pattern="^(and|or)$"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    kw = [k.strip() for k in keywords.split(",") if k.strip()]
    total, rows = await keyword_search(db, keywords=kw, mode=mode, page=page, size=size)
    if not rows:
        return PaginatedTasks(total=total, page=page, size=size, items=[])

    ids = [r["id"] for r in rows]
    tasks_res = await db.execute(
        select(Task).where(Task.id.in_(ids)).options(selectinload(Task.solution_method))
    )
    by_id = {t.id: t for t in tasks_res.scalars().all()}
    items = []
    for r in rows:
        t = by_id.get(r["id"])
        if not t:
            continue
        items.append(
            TaskListItem(
                id=t.id,
                title=_display_title(t),
                difficulty=t.difficulty,
                solution_method=_method_ref(t),
                snippet=r.get("snippet"),
                rank=float(r["rank"]),
            )
        )
    return PaginatedTasks(total=total, page=page, size=size, items=items)


@router.get("/tasks/{task_id}", response_model=TaskDetail)
async def get_task(task_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(Task)
        .where(Task.id == task_id)
        .options(
            selectinload(Task.solution_method),
            selectinload(Task.task_topics).selectinload(TaskTopic.topic),
            selectinload(Task.olympiad),
            selectinload(Task.solutions),
            selectinload(Task.hints),
            selectinload(Task.sources),
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    topics = [
        TopicRef(id=tt.topic.id, name=tt.topic.name, path=tt.topic.path)
        for tt in task.task_topics
    ]
    olympiads = ([OlympiadRef(id=task.olympiad.id, name=task.olympiad.name,
                              short_name=task.olympiad.short_name)] if task.olympiad else [])
    sm = task.solution_method
    return TaskDetail(
        id=task.id,
        title=_display_title(task),
        statement=task.statement,
        answer=task.answer,
        difficulty=task.difficulty,
        subject=task.subject,
        grade=task.grade,
        classifier=task.classifier,
        problem_type=task.problem_type,
        topics=topics,
        olympiads=olympiads,
        solution_method=(
            SolutionMethodRef(id=sm.id, name=sm.name, path=sm.path) if sm else None
        ),
        source=SourceInfo(
            system=task.sources[0].source_system if task.sources else None,
            external_id=task.sources[0].external_id if task.sources else None,
            url=task.sources[0].url if task.sources else None,
            subject=task.subject,
            grade=task.grade,
            year=task.source_year,
            stage=task.source_stage,
            number=task.source_problem_number,
        ),
        has_solution=any(s.is_verified or not s.is_generated for s in task.solutions),
        hints_count=len(task.hints),
    )


@router.get("/tasks/{task_id}/similar", response_model=SimilarTasksResponse)
async def get_similar_tasks(
    task_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(10, ge=1, le=50),
):
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    items = await similar_tasks(db, task, limit)
    return SimilarTasksResponse(
        items=[
            {"id": i["id"], "title": i["title"], "score": float(i["score"])}
            for i in items
        ]
    )


@router.post("/tasks/{task_id}/topics", response_model=StatusOk)
async def assign_topics(
    task_id: uuid.UUID,
    body: AssignTopicsRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.execute(delete(TaskTopic).where(TaskTopic.task_id == task_id))
    for item in body.topics:
        db.add(TaskTopic(task_id=task_id, topic_id=item.id, weight=item.weight))
    await db.commit()
    return StatusOk()


@router.post("/tasks/{task_id}/olympiads", response_model=StatusOk)
async def assign_olympiads(
    task_id: uuid.UUID,
    body: AssignOlympiadsRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if len(body.olympiad_ids) > 1:
        raise HTTPException(status_code=422, detail="A task can belong to only one olympiad")
    task.olympiad_id = body.olympiad_ids[0] if body.olympiad_ids else None
    await db.commit()
    return StatusOk()


@router.post("/tasks/{task_id}/solution-method", response_model=StatusOk)
async def assign_solution_method(
    task_id: uuid.UUID,
    body: AssignSolutionMethodRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    task.solution_method_id = body.solution_method_id
    await db.commit()
    return StatusOk()


@router.get("/tasks/{task_id}/hints", response_model=HintResponse)
async def get_hint(
    task_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    level: int = Query(1, ge=1),
):
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    result = await db.execute(
        select(Hint).where(Hint.task_id == task_id, Hint.level == level)
    )
    hint = result.scalar_one_or_none()
    if hint:
        return HintResponse(
            task_id=task_id,
            level=level,
            content=hint.content,
            is_verified=hint.is_verified,
            cached=True,
        )

    content = generate_hint(task.statement, level)
    hint = Hint(task_id=task_id, level=level, content=content, is_verified=False)
    db.add(hint)
    await db.commit()
    return HintResponse(
        task_id=task_id,
        level=level,
        content=content,
        is_verified=False,
        cached=False,
    )


@router.post("/tasks/{task_id}/hints/{level}/verify", response_model=StatusOk)
async def verify_hint(
    task_id: uuid.UUID,
    level: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Hint).where(Hint.task_id == task_id, Hint.level == level)
    )
    hint = result.scalar_one_or_none()
    if hint is None:
        raise HTTPException(status_code=404, detail="Hint not found")
    hint.is_verified = True
    await db.commit()
    return StatusOk()


@router.get("/tasks/{task_id}/solutions", response_model=SolutionsResponse)
async def list_solutions(
    task_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    only_verified: bool = False,
):
    q = select(Solution).where(Solution.task_id == task_id)
    if only_verified:
        q = q.where(Solution.is_verified.is_(True))
    result = await db.execute(q.order_by(Solution.created_at.desc()))
    items = [
        SolutionItem(
            id=s.id,
            content=s.content,
            is_generated=s.is_generated,
            is_verified=s.is_verified,
        )
        for s in result.scalars().all()
    ]
    return SolutionsResponse(items=items)


@router.post("/tasks/{task_id}/solutions/generate", response_model=GenerateSolutionResponse)
async def generate_task_solution(
    task_id: uuid.UUID,
    body: GenerateSolutionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    content = generate_solution(task.statement, body.style, body.steps)
    sol = Solution(task_id=task_id, content=content, is_generated=True, is_verified=False)
    db.add(sol)
    await db.commit()
    await db.refresh(sol)
    return GenerateSolutionResponse(solution_id=sol.id, content=content)


@router.post("/tasks", response_model=CreateTaskResponse)
async def create_task(
    body: CreateTaskRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
):
    task = Task(
        title=body.title,
        statement=body.statement,
        answer=body.answer,
        difficulty=body.difficulty,
        subject=body.subject,
        grade=body.grade,
        classifier=body.classifier,
        problem_type=body.problem_type,
        status=body.status,
        solution_method_id=body.solution_method_id,
        source_stage=body.source_stage,
        source_year=body.source_year,
        source_problem_number=body.source_problem_number,
    )
    db.add(task)
    await db.flush()
    for tid in body.topics:
        db.add(TaskTopic(task_id=task.id, topic_id=tid))
    await db.commit()
    await db.refresh(task)

    async def _embed():
        async with SessionLocal() as session:
            await compute_and_store_task_embedding(session, task.id)

    if settings.aitunnel_api_key:
        background_tasks.add_task(_embed)
    return CreateTaskResponse(id=task.id)


@router.put("/tasks/{task_id}", response_model=StatusOk)
async def update_task(
    task_id: uuid.UUID,
    body: UpdateTaskRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
):
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    needs_reindex = bool({"statement", "classifier"} & body.model_fields_set)
    if needs_reindex:
        await db.execute(delete(TaskEmbedding).where(
            TaskEmbedding.task_id == task_id, TaskEmbedding.kind == "topic"
        ))
    await db.commit()
    if needs_reindex and task.status == "published" and settings.aitunnel_api_key:
        async def _embed():
            async with SessionLocal() as session:
                await compute_and_store_task_embedding(session, task_id)
        background_tasks.add_task(_embed)
    return StatusOk()


@router.post("/tasks/{task_id}/embedding", response_model=EmbeddingQueuedResponse)
async def recompute_task_embedding(
    task_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    async def _job():
        async with SessionLocal() as session:
            await compute_and_store_task_embedding(session, task_id)

    if not settings.aitunnel_api_key:
        raise HTTPException(status_code=503, detail="AITUNNEL_API_KEY не задан")
    background_tasks.add_task(_job)
    return EmbeddingQueuedResponse()


@router.post("/tasks/{task_id}/difficulty", response_model=SetDifficultyResponse)
async def set_difficulty(
    task_id: uuid.UUID,
    body: SetDifficultyRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    task.difficulty = body.difficulty
    await db.commit()
    return SetDifficultyResponse(task_id=task_id, difficulty=body.difficulty)


@router.post("/tasks/{task_id}/check")
async def check_task_solution(
    task_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
):
    task = await db.get(Task, task_id)

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if not file.filename:
        raise HTTPException(status_code=400, detail="File is required")

    import os
    import tempfile

    suffix = os.path.splitext(file.filename)[1].lower()

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        content = await file.read()
        temp_file.write(content)
        temp_path = temp_file.name

    try:
        prompt = f"""
Ты проверяешь решение олимпиадной математической задачи.

Условие задачи:
{task.statement}

Во вложенном файле находится решение ученика.

Проверь решение и верни ответ строго в формате JSON с двумя полями:

- "text" — текстовый разбор решения по следующей структуре:
    1. Вердикт: верно / неверно / частично верно.
    2. Какие шаги решения правильные.
    3. Какие ошибки допущены.
    4. Как исправить ошибки.
    5. Итоговый правильный ответ, если его можно определить.
- "verdict" — целое число: 0, если задача зачтена (решение и ответ верные),
  1, если задача не зачтена (решение или ответ неверные).

Не придумывай отсутствующие в решении шаги и не выдавай полное решение вместо проверки.
"""

        parsed = check_solution(temp_path, prompt)

        return {
            "task_id": str(task_id),
            "filename": file.filename,
            "result": parsed.get("text", ""),
            "verdict": parsed.get("verdict", 1),
        }

    finally:
        os.remove(temp_path)