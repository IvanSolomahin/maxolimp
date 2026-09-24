import uuid

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SolutionMethod
from app.services.topic_paths import _UNSET, depth_from_path, path_segment


async def resolve_solution_method_path(
    session: AsyncSession,
    *,
    name: str,
    parent_id: uuid.UUID | None,
) -> tuple[str, int]:
    segment = path_segment(name)
    if parent_id is None:
        return segment, 0
    parent = await session.get(SolutionMethod, parent_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Parent solution method not found")
    return f"{parent.path}/{segment}", parent.depth + 1


async def is_ancestor(
    session: AsyncSession, ancestor_id: uuid.UUID, node_id: uuid.UUID
) -> bool:
    node = await session.get(SolutionMethod, node_id)
    if node is None:
        return False
    ancestor = await session.get(SolutionMethod, ancestor_id)
    if ancestor is None:
        return False
    return node.path == ancestor.path or node.path.startswith(f"{ancestor.path}/")


async def repath_subtree(session: AsyncSession, old_path: str, new_path: str) -> None:
    result = await session.execute(
        select(SolutionMethod).where(
            or_(SolutionMethod.path == old_path, SolutionMethod.path.like(f"{old_path}/%"))
        )
    )
    for row in result.scalars().all():
        if row.path == old_path:
            row.path = new_path
        else:
            row.path = new_path + row.path[len(old_path) :]
        row.depth = depth_from_path(row.path)


async def apply_solution_method_location(
    session: AsyncSession,
    method: SolutionMethod,
    *,
    name: str | None = None,
    parent_id: uuid.UUID | None | object = _UNSET,
) -> None:
    new_name = name if name is not None else method.name
    if parent_id is _UNSET:
        new_parent_id = method.parent_id
    else:
        new_parent_id = parent_id

    if new_parent_id == method.id:
        raise HTTPException(status_code=400, detail="Solution method cannot be its own parent")
    if new_parent_id is not None and await is_ancestor(session, method.id, new_parent_id):
        raise HTTPException(
            status_code=400, detail="Cannot move solution method under its descendant"
        )

    new_path, new_depth = await resolve_solution_method_path(
        session, name=new_name, parent_id=new_parent_id
    )
    old_path = method.path
    method.name = new_name
    method.parent_id = new_parent_id
    if new_path != old_path:
        await repath_subtree(session, old_path, new_path)
    else:
        method.path = new_path
        method.depth = new_depth
