import uuid
from typing import Any

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models import SolutionMethod, Task, TaskOlympiad, TaskTopic, Topic
from app.services.embeddings import embed_text, vector_to_pg


def _snippet(statement: str, max_len: int = 160) -> str:
    s = statement.strip().replace("\n", " ")
    return s if len(s) <= max_len else s[: max_len - 1] + "…"


def _task_filters_sql(prefix: str = "t") -> str:
    return f"""
        (CAST(:difficulty_min AS SMALLINT) IS NULL
            OR {prefix}.difficulty >= CAST(:difficulty_min AS SMALLINT))
        AND (CAST(:difficulty_max AS SMALLINT) IS NULL
            OR {prefix}.difficulty <= CAST(:difficulty_max AS SMALLINT))
        AND (CAST(:year_from AS SMALLINT) IS NULL
            OR {prefix}.source_year >= CAST(:year_from AS SMALLINT))
        AND (CAST(:year_to AS SMALLINT) IS NULL
            OR {prefix}.source_year <= CAST(:year_to AS SMALLINT))
        AND (CAST(:stage AS TEXT) IS NULL
            OR {prefix}.source_stage = CAST(:stage AS TEXT))
        AND (CAST(:solution_method_id AS UUID) IS NULL
            OR {prefix}.solution_method_id = CAST(:solution_method_id AS UUID))
        AND ({prefix}.status = 'published' OR CAST(:include_draft AS BOOLEAN) IS TRUE)
    """


def _filter_params(
    *,
    difficulty_min: int | None,
    difficulty_max: int | None,
    year_from: int | None,
    year_to: int | None,
    stage: str | None,
    solution_method_id: uuid.UUID | None,
    include_draft: bool = False,
) -> dict[str, Any]:
    return {
        "difficulty_min": difficulty_min,
        "difficulty_max": difficulty_max,
        "year_from": year_from,
        "year_to": year_to,
        "stage": stage,
        "solution_method_id": solution_method_id,
        "include_draft": include_draft,
    }


async def hybrid_search_tasks(
    session: AsyncSession,
    *,
    q: str | None,
    difficulty_min: int | None,
    difficulty_max: int | None,
    year_from: int | None,
    year_to: int | None,
    stage: str | None,
    solution_method_id: uuid.UUID | None,
    sort: str,
    page: int,
    size: int,
) -> tuple[int, list[dict]]:
    offset = (page - 1) * size
    params = _filter_params(
        difficulty_min=difficulty_min,
        difficulty_max=difficulty_max,
        year_from=year_from,
        year_to=year_to,
        stage=stage,
        solution_method_id=solution_method_id,
    )
    params["limit"] = size
    params["offset"] = offset
    params["rrf_k"] = settings.rrf_k

    if q and q.strip():
        params["q"] = q.strip()
        params["query_vec"] = vector_to_pg(embed_text(params["q"]))
        sql = f"""
        WITH fts AS (
            SELECT t.id,
                   ROW_NUMBER() OVER (
                       ORDER BY ts_rank(t.search_vector, plainto_tsquery('russian', :q)) DESC
                   ) AS rn
            FROM tasks t
            WHERE t.search_vector @@ plainto_tsquery('russian', :q)
              AND {_task_filters_sql("t")}
            LIMIT 500
        ),
        vec AS (
            SELECT id, rn FROM (
                SELECT t.id,
                       ROW_NUMBER() OVER (ORDER BY t.embedding <=> :query_vec::vector) AS rn
                FROM tasks t
                WHERE t.embedding IS NOT NULL
                  AND {_task_filters_sql("t")}
            ) vsub
            WHERE rn <= 500
        ),
        rrf AS (
            SELECT COALESCE(f.id, v.id) AS id,
                   COALESCE(1.0 / (CAST(:rrf_k AS INTEGER) + f.rn), 0)
                       + COALESCE(1.0 / (CAST(:rrf_k AS INTEGER) + v.rn), 0) AS score
            FROM fts f
            FULL OUTER JOIN vec v ON f.id = v.id
        ),
        ranked AS (
            SELECT r.id, r.score,
                   ts_headline(
                       'russian',
                       t.statement,
                       plainto_tsquery('russian', :q),
                       'MaxWords=20, MinWords=5'
                   ) AS snippet
            FROM rrf r
            JOIN tasks t ON t.id = r.id
        )
        SELECT COUNT(*) OVER () AS total_count,
               ranked.id,
               ranked.score,
               ranked.snippet
        FROM ranked
        ORDER BY
            CASE WHEN CAST(:sort AS TEXT) = 'newest' THEN 0 ELSE 1 END,
            CASE WHEN CAST(:sort AS TEXT) = 'newest'
                THEN (SELECT created_at FROM tasks WHERE id = ranked.id) END DESC NULLS LAST,
            CASE WHEN CAST(:sort AS TEXT) = 'difficulty' THEN 0 ELSE 1 END,
            CASE WHEN CAST(:sort AS TEXT) = 'difficulty'
                THEN (SELECT difficulty FROM tasks WHERE id = ranked.id) END ASC NULLS LAST,
            ranked.score DESC
        LIMIT CAST(:limit AS INTEGER) OFFSET CAST(:offset AS INTEGER)
        """
        params["sort"] = sort
        result = await session.execute(text(sql), params)
        rows = result.mappings().all()
        if not rows:
            return 0, []
        total = int(rows[0]["total_count"])
        return total, [dict(r) for r in rows]

    order_clause = {
        "newest": "t.created_at DESC",
        "difficulty": "t.difficulty ASC, t.created_at DESC",
        "relevance": "t.created_at DESC",
    }.get(sort, "t.created_at DESC")

    count_sql = f"""
        SELECT COUNT(*) FROM tasks t
        WHERE {_task_filters_sql("t")}
    """
    count_res = await session.execute(text(count_sql), params)
    total = int(count_res.scalar_one())

    list_sql = f"""
        SELECT t.id, NULL::float AS score, LEFT(t.statement, 160) AS snippet
        FROM tasks t
        WHERE {_task_filters_sql("t")}
        ORDER BY {order_clause}
        LIMIT CAST(:limit AS INTEGER) OFFSET CAST(:offset AS INTEGER)
    """
    list_res = await session.execute(text(list_sql), params)
    return total, [dict(r) for r in list_res.mappings().all()]


async def keyword_search(
    session: AsyncSession,
    *,
    keywords: list[str],
    mode: str,
    page: int,
    size: int,
) -> tuple[int, list[dict]]:
    if not keywords:
        return 0, []
    parts = [k.strip() for k in keywords if k.strip()]
    if not parts:
        return 0, []

    if mode == "and":
        tsq = " & ".join(parts)
    else:
        tsq = " | ".join(parts)

    offset = (page - 1) * size
    sql = """
    WITH matched AS (
        SELECT t.id,
               ts_rank(t.search_vector, to_tsquery('russian', :tsq)) AS rank,
               ts_headline(
                   'russian', t.statement, to_tsquery('russian', :tsq),
                   'MaxWords=20, MinWords=5'
               ) AS snippet
        FROM tasks t
        WHERE t.status = 'published'
          AND t.search_vector @@ to_tsquery('russian', :tsq)
    )
    SELECT COUNT(*) OVER () AS total_count, id, rank, snippet
    FROM matched
    ORDER BY rank DESC
    LIMIT CAST(:limit AS INTEGER) OFFSET CAST(:offset AS INTEGER)
    """
    result = await session.execute(
        text(sql),
        {"tsq": tsq, "limit": size, "offset": offset},
    )
    rows = result.mappings().all()
    if not rows:
        return 0, []
    return int(rows[0]["total_count"]), [dict(r) for r in rows]


async def tasks_by_topics(
    session: AsyncSession,
    *,
    topic_ids: list[uuid.UUID],
    include_subtopics: bool,
    match: str,
    page: int,
    size: int,
) -> tuple[int, list[Task]]:
    if not topic_ids:
        return 0, []

    topic_id_set: set[uuid.UUID] = set(topic_ids)
    if include_subtopics:
        for tid in topic_ids:
            topic = await session.get(Topic, tid)
            if topic:
                sub = await session.execute(
                    select(Topic.id).where(
                        or_(Topic.id == tid, Topic.path.like(f"{topic.path}/%"))
                    )
                )
                topic_id_set.update(sub.scalars().all())

    offset = (page - 1) * size
    base = (
        select(Task)
        .join(TaskTopic, TaskTopic.task_id == Task.id)
        .where(TaskTopic.topic_id.in_(topic_id_set), Task.status == "published")
        .options(selectinload(Task.solution_method))
    )
    if match == "all":
        subq = (
            select(TaskTopic.task_id)
            .where(TaskTopic.topic_id.in_(topic_id_set))
            .group_by(TaskTopic.task_id)
            .having(func.count(func.distinct(TaskTopic.topic_id)) >= len(topic_ids))
        )
        base = base.where(Task.id.in_(subq))

    count_q = select(func.count()).select_from(base.distinct().subquery())
    total = int((await session.execute(count_q)).scalar_one())

    items_q = (
        base.distinct()
        .order_by(Task.created_at.desc())
        .limit(size)
        .offset(offset)
    )
    tasks = list((await session.execute(items_q)).scalars().all())
    return total, tasks


async def tasks_by_olympiads(
    session: AsyncSession,
    *,
    olympiad_ids: list[uuid.UUID],
    year_from: int | None,
    year_to: int | None,
    stage: str | None,
    page: int,
    size: int,
) -> tuple[int, list[Task]]:
    if not olympiad_ids:
        return 0, []

    offset = (page - 1) * size
    q = (
        select(Task)
        .join(TaskOlympiad, TaskOlympiad.task_id == Task.id)
        .where(TaskOlympiad.olympiad_id.in_(olympiad_ids), Task.status == "published")
        .options(selectinload(Task.solution_method))
    )
    if year_from is not None:
        q = q.where(Task.source_year >= year_from)
    if year_to is not None:
        q = q.where(Task.source_year <= year_to)
    if stage is not None:
        q = q.where(Task.source_stage == stage)

    count_q = select(func.count()).select_from(q.distinct().subquery())
    total = int((await session.execute(count_q)).scalar_one())

    tasks = list(
        (
            await session.execute(
                q.distinct().order_by(Task.created_at.desc()).limit(size).offset(offset)
            )
        ).scalars().all()
    )
    return total, tasks


async def similar_tasks(
    session: AsyncSession,
    task: Task,
    limit: int,
) -> list[dict]:
    if task.embedding is None:
        return []
    vec = vector_to_pg(list(task.embedding))
    sql = """
    SELECT t.id, t.title, 1 - (t.embedding <=> :vec::vector) AS score
    FROM tasks t
    WHERE t.id <> CAST(:task_id AS UUID)
      AND t.embedding IS NOT NULL
      AND t.status = 'published'
    ORDER BY t.embedding <=> :vec::vector
    LIMIT CAST(:limit AS INTEGER)
    """
    result = await session.execute(
        text(sql),
        {"vec": vec, "task_id": task.id, "limit": limit},
    )
    return [dict(r) for r in result.mappings().all()]


async def load_solution_method_map(
    session: AsyncSession, method_ids: set[uuid.UUID]
) -> dict[uuid.UUID, SolutionMethod]:
    if not method_ids:
        return {}
    res = await session.execute(select(SolutionMethod).where(SolutionMethod.id.in_(method_ids)))
    return {m.id: m for m in res.scalars().all()}
