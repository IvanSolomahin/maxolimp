import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SolutionMethod, Topic
from app.schemas import SolutionMethodTreeNode, TopicTreeNode


def build_tree(rows, flat: bool, depth_max: int | None, node_cls: type) -> list:
    by_parent: dict[uuid.UUID | None, list] = {}
    for row in rows:
        by_parent.setdefault(row.parent_id, []).append(row)

    def make_node(row):
        if depth_max is not None and row.depth > depth_max:
            return None
        children = []
        for c in sorted(by_parent.get(row.id, []), key=lambda x: x.name):
            node = make_node(c)
            if node is not None:
                children.append(node)
        return node_cls(
            id=row.id,
            name=row.name,
            path=row.path,
            depth=row.depth,
            children=[] if flat else children,
        )

    if flat:
        filtered = [r for r in rows if depth_max is None or r.depth <= depth_max]
        return [
            node_cls(id=r.id, name=r.name, path=r.path, depth=r.depth, children=[])
            for r in sorted(filtered, key=lambda x: x.path)
        ]

    out = []
    for r in sorted(by_parent.get(None, []), key=lambda x: x.name):
        node = make_node(r)
        if node is not None:
            out.append(node)
    return out


def _filter_subtree(rows, parent_path: str | None) -> list:
    if parent_path is None:
        return rows
    prefix = parent_path + "/"
    return [r for r in rows if r.path == parent_path or r.path.startswith(prefix)]


def _subtree_from_parent(rows, parent, node_cls, depth_max: int | None):
    def make_from(parent_row):
        if depth_max is not None and parent_row.depth > depth_max:
            return None
        children = []
        for c in sorted([x for x in rows if x.parent_id == parent_row.id], key=lambda x: x.name):
            node = make_from(c)
            if node is not None:
                children.append(node)
        return node_cls(
            id=parent_row.id,
            name=parent_row.name,
            path=parent_row.path,
            depth=parent_row.depth,
            children=children,
        )

    node = make_from(parent)
    return [node] if node else []


async def fetch_topics_tree(
    session: AsyncSession,
    *,
    flat: bool,
    parent_id: uuid.UUID | None,
    depth_max: int | None,
) -> list[TopicTreeNode]:
    result = await session.execute(select(Topic).order_by(Topic.path))
    rows = list(result.scalars().all())
    if parent_id is not None:
        parent = await session.get(Topic, parent_id)
        if parent is None:
            return []
        rows = _filter_subtree(rows, parent.path)
        if not flat:
            return _subtree_from_parent(rows, parent, TopicTreeNode, depth_max)
    return build_tree(rows, flat=flat, depth_max=depth_max, node_cls=TopicTreeNode)


async def fetch_solution_methods_tree(
    session: AsyncSession,
    *,
    flat: bool,
    parent_id: uuid.UUID | None,
    depth_max: int | None,
) -> list[SolutionMethodTreeNode]:
    result = await session.execute(select(SolutionMethod).order_by(SolutionMethod.path))
    rows = list(result.scalars().all())
    if parent_id is not None:
        parent = await session.get(SolutionMethod, parent_id)
        if parent is None:
            return []
        rows = _filter_subtree(rows, parent.path)
        if not flat:
            return _subtree_from_parent(rows, parent, SolutionMethodTreeNode, depth_max)
    return build_tree(rows, flat=flat, depth_max=depth_max, node_cls=SolutionMethodTreeNode)
