import uuid
from typing import Any

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models import SolutionMethod, Task, TaskTopic, Topic
from app.services.embeddings import embed_text, vector_to_pg


def _snippet(statement: str, max_len: int = 160) -> str:
    s = statement.strip().replace("\n", " ")
    if len(s) <= max_len:
        return s
    cut = max_len - 1
    # Do not leave a generated title or search snippet inside an inline formula.
    if s[:cut].count("$") % 2:
        opening = s.rfind("$", 0, cut)
        if opening > 0:
            cut = opening
        else:
            closing = s.find("$", cut)
            if 0 <= closing < max_len * 3:
                cut = closing + 1
            else:
                cut = 0
    return s[:cut].rstrip() + "…"


def _task_filters_sql(prefix: str = "t") -> str:
    return f"""
        (CAST(:subject AS TEXT) IS NULL OR {prefix}.subject = CAST(:subject AS TEXT))
        AND (CAST(:grade AS SMALLINT) IS NULL OR {prefix}.grade = CAST(:grade AS SMALLINT))
        AND
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
    subject: str | None = None,
    grade: int | None = None,
) -> dict[str, Any]:
    return {
        "subject": subject,
        "grade": grade,
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
    subject: str | None = None,
    grade: int | None = None,
    mode: str = "topic",
) -> tuple[int, list[dict]]:
    offset = (page - 1) * size
    params = _filter_params(
        difficulty_min=difficulty_min,
        difficulty_max=difficulty_max,
        year_from=year_from,
        year_to=year_to,
        stage=stage,
        solution_method_id=solution_method_id,
        subject=subject,
        grade=grade,
    )
    params["limit"] = size
    params["offset"] = offset
    params["rrf_k"] = settings.rrf_k

    if q and q.strip():
        params["q"] = q.strip()
        query = params["q"]
        can_embed = bool(settings.aitunnel_api_key)
        if can_embed:
            params["query_vec"] = vector_to_pg(await embed_text(query))
        params["model"] = settings.embedding_model
        params["dimensions"] = settings.embedding_dimension
        params["mode"] = mode
        kind_filter = "e.kind = 'topic'" if mode == "topic" else "e.kind = 'solution'" if mode == "solution" else "e.kind IN ('topic', 'solution')"
        vector_cte = ""
        vector_union = ""
        if can_embed:
            vector_cte = f"""
        , vec AS (
            SELECT id, row_number() OVER (ORDER BY distance) AS rn FROM (
                SELECT e.task_id AS id,
                       e.embedding::halfvec(2560) <=> CAST(:query_vec AS halfvec(2560)) AS distance
                FROM task_embeddings e JOIN tasks t ON t.id = e.task_id
                WHERE {kind_filter} AND e.model = CAST(:model AS TEXT)
                  AND e.dimensions = CAST(:dimensions AS INTEGER) AND {_task_filters_sql('t')}
                ORDER BY e.embedding::halfvec(2560) <=> CAST(:query_vec AS halfvec(2560))
                LIMIT 500
            ) candidates
        )
            """
            vector_union = "UNION ALL SELECT id, 1.0 / (CAST(:rrf_k AS INTEGER) + rn) FROM vec"
        sql = f"""
        WITH fts AS (
            SELECT t.id,
                   ROW_NUMBER() OVER (
                       ORDER BY GREATEST(
                           CASE WHEN :mode IN ('topic', 'both') THEN ts_rank(t.topic_search_vector, plainto_tsquery('russian', :q)) ELSE 0 END,
                           CASE WHEN :mode IN ('solution', 'both') THEN COALESCE((
                               SELECT max(ts_rank(s.search_vector, plainto_tsquery('russian', :q)))
                               FROM solutions s WHERE s.task_id = t.id AND NOT s.is_generated
                           ), 0) ELSE 0 END
                       ) DESC
                   ) AS rn
            FROM tasks t
            WHERE ((:mode IN ('topic', 'both') AND t.topic_search_vector @@ plainto_tsquery('russian', :q))
                OR (:mode IN ('solution', 'both') AND EXISTS (
                    SELECT 1 FROM solutions s WHERE s.task_id = t.id AND NOT s.is_generated
                    AND s.search_vector @@ plainto_tsquery('russian', :q))))
              AND {_task_filters_sql("t")}
            ORDER BY GREATEST(
                CASE WHEN :mode IN ('topic', 'both') THEN ts_rank(t.topic_search_vector, plainto_tsquery('russian', :q)) ELSE 0 END,
                CASE WHEN :mode IN ('solution', 'both') THEN COALESCE((
                    SELECT max(ts_rank(s.search_vector, plainto_tsquery('russian', :q)))
                    FROM solutions s WHERE s.task_id = t.id AND NOT s.is_generated
                ), 0) ELSE 0 END
            ) DESC
            LIMIT 500
        )
        {vector_cte},
        rrf AS (
            SELECT id, sum(part_score) AS score FROM (
                SELECT id, 1.0 / (CAST(:rrf_k AS INTEGER) + rn) AS part_score FROM fts
                {vector_union}
            ) hits GROUP BY id
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
               ts_rank(t.topic_search_vector, to_tsquery('russian', :tsq)) AS rank,
               ts_headline(
                   'russian', t.statement, to_tsquery('russian', :tsq),
                   'MaxWords=20, MinWords=5'
               ) AS snippet
        FROM tasks t
        WHERE t.status = 'published'
          AND t.topic_search_vector @@ to_tsquery('russian', :tsq)
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
        .where(Task.olympiad_id.in_(olympiad_ids), Task.status == "published")
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
    sql = """
    SELECT t.id, COALESCE(t.title, LEFT(t.statement, 100)) AS title,
           1 - (e.embedding <=> source.embedding) AS score
    FROM task_embeddings source
    JOIN task_embeddings e ON e.kind = source.kind AND e.model = source.model
        AND e.dimensions = source.dimensions
    JOIN tasks t ON t.id = e.task_id
    WHERE source.task_id = CAST(:task_id AS UUID)
      AND source.kind = 'topic' AND source.model = CAST(:model AS TEXT)
      AND source.dimensions = 2560
      AND t.id <> source.task_id
      AND t.status = 'published'
    ORDER BY e.embedding::halfvec(2560) <=> source.embedding::halfvec(2560)
    LIMIT CAST(:limit AS INTEGER)
    """
    result = await session.execute(
        text(sql),
        {"task_id": task.id, "model": settings.embedding_model, "limit": limit},
    )
    return [dict(r) for r in result.mappings().all()]


async def load_solution_method_map(
    session: AsyncSession, method_ids: set[uuid.UUID]
) -> dict[uuid.UUID, SolutionMethod]:
    if not method_ids:
        return {}
    res = await session.execute(select(SolutionMethod).where(SolutionMethod.id.in_(method_ids)))
    return {m.id: m for m in res.scalars().all()}
