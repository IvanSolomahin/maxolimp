import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import SolutionMethod
from app.schemas import (
    CreateEntityResponse,
    CreateSolutionMethodRequest,
    SolutionMethodRef,
    SolutionMethodsResponse,
    StatusOk,
    UpdateSolutionMethodRequest,
)
from app.services.hierarchy import fetch_solution_methods_tree
from app.services.solution_method_paths import (
    apply_solution_method_location,
    resolve_solution_method_path,
)
from app.services.topic_paths import _UNSET

router = APIRouter(tags=["solution-methods"])


@router.get("/solution-methods", response_model=SolutionMethodsResponse)
async def list_solution_methods(
    db: Annotated[AsyncSession, Depends(get_db)],
    flat: bool = False,
    parent_id: uuid.UUID | None = None,
    depth_max: int | None = None,
):
    items = await fetch_solution_methods_tree(
        db, flat=flat, parent_id=parent_id, depth_max=depth_max
    )
    return SolutionMethodsResponse(items=items)


@router.post("/solution-methods", response_model=CreateEntityResponse)
async def create_solution_method(
    body: CreateSolutionMethodRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    path, depth = await resolve_solution_method_path(
        db, name=body.name, parent_id=body.parent_id
    )
    method = SolutionMethod(
        name=body.name,
        parent_id=body.parent_id,
        path=path,
        depth=depth,
    )
    db.add(method)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Solution method with this name already exists under the same parent",
        ) from exc
    await db.refresh(method)
    return CreateEntityResponse(id=method.id)


@router.patch("/solution-methods/{method_id}", response_model=SolutionMethodRef)
async def update_solution_method(
    method_id: uuid.UUID,
    body: UpdateSolutionMethodRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    method = await db.get(SolutionMethod, method_id)
    if method is None:
        raise HTTPException(status_code=404, detail="Solution method not found")

    data = body.model_dump(exclude_unset=True)
    if not data:
        return SolutionMethodRef(id=method.id, name=method.name, path=method.path)

    await apply_solution_method_location(
        db,
        method,
        name=data.get("name"),
        parent_id=data["parent_id"] if "parent_id" in data else _UNSET,
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Solution method with this name already exists under the same parent",
        ) from exc
    await db.refresh(method)
    return SolutionMethodRef(id=method.id, name=method.name, path=method.path)


@router.delete("/solution-methods/{method_id}", response_model=StatusOk)
async def delete_solution_method(
    method_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    method = await db.get(SolutionMethod, method_id)
    if method is None:
        raise HTTPException(status_code=404, detail="Solution method not found")

    children = await db.execute(
        select(func.count())
        .select_from(SolutionMethod)
        .where(SolutionMethod.parent_id == method_id)
    )
    if int(children.scalar_one()) > 0:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete solution method with children; remove or move them first",
        )

    await db.delete(method)
    await db.commit()
    return StatusOk()
