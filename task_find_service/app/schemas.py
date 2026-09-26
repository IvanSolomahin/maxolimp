import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class StatusOk(BaseModel):
    status: Literal["ok"] = "ok"


class SolutionMethodRef(BaseModel):
    id: uuid.UUID
    name: str
    path: str | None = None


class TopicRef(BaseModel):
    id: uuid.UUID
    name: str
    path: str


class OlympiadRef(BaseModel):
    id: uuid.UUID
    name: str
    short_name: str | None


class SourceInfo(BaseModel):
    system: str | None = None
    external_id: str | None = None
    url: str | None = None
    subject: str | None = None
    grade: int | None = None
    year: int | None = None
    stage: str | None = None
    number: str | None = None


class TaskListItem(BaseModel):
    id: uuid.UUID
    title: str
    difficulty: int | None
    solution_method: SolutionMethodRef | None = None
    snippet: str | None = None
    number: str | None = None
    olympiad: str | None = None
    olympiad_short_name: str | None = None
    score: float | None = None
    rank: float | None = None


class PaginatedTasks(BaseModel):
    total: int
    page: int
    size: int
    items: list[TaskListItem]


class TaskDetail(BaseModel):
    id: uuid.UUID
    title: str
    statement: str
    answer: str | None
    difficulty: int | None
    subject: str | None = None
    grade: int | None = None
    classifier: str | None = None
    problem_type: str | None = None
    topics: list[TopicRef]
    olympiads: list[OlympiadRef]
    solution_method: SolutionMethodRef | None
    source: SourceInfo
    has_solution: bool
    hints_count: int


class SimilarTaskItem(BaseModel):
    id: uuid.UUID
    title: str
    score: float


class SimilarTasksResponse(BaseModel):
    items: list[SimilarTaskItem]


class TopicWeightInput(BaseModel):
    id: uuid.UUID
    weight: float = 1.0


class AssignTopicsRequest(BaseModel):
    topics: list[TopicWeightInput]


class AssignOlympiadsRequest(BaseModel):
    olympiad_ids: list[uuid.UUID]


class AssignSolutionMethodRequest(BaseModel):
    solution_method_id: uuid.UUID | None


class TopicTreeNode(BaseModel):
    id: uuid.UUID
    name: str
    path: str
    depth: int
    children: list["TopicTreeNode"] = Field(default_factory=list)


TopicTreeNode.model_rebuild()


class TopicsResponse(BaseModel):
    items: list[TopicTreeNode]


class SolutionMethodTreeNode(BaseModel):
    id: uuid.UUID
    name: str
    path: str
    depth: int
    children: list["SolutionMethodTreeNode"] = Field(default_factory=list)


SolutionMethodTreeNode.model_rebuild()


class SolutionMethodsResponse(BaseModel):
    items: list[SolutionMethodTreeNode]


class OlympiadsResponse(BaseModel):
    items: list[OlympiadRef]


class HintResponse(BaseModel):
    task_id: uuid.UUID
    level: int
    content: str
    is_verified: bool
    cached: bool


class SolutionItem(BaseModel):
    id: uuid.UUID
    content: str
    is_generated: bool
    is_verified: bool


class SolutionsResponse(BaseModel):
    items: list[SolutionItem]


class GenerateSolutionRequest(BaseModel):
    style: str = "olymp"
    steps: bool = True


class GenerateSolutionResponse(BaseModel):
    solution_id: uuid.UUID
    content: str
    is_generated: bool = True


class CreateTaskRequest(BaseModel):
    title: str | None = None
    statement: str
    answer: str | None = None
    difficulty: int | None = Field(default=None, ge=1, le=10)
    subject: Literal["math", "physics"] | None = None
    grade: int | None = None
    classifier: str | None = None
    problem_type: str | None = None
    status: str = "draft"
    topics: list[uuid.UUID] = Field(default_factory=list)
    solution_method_id: uuid.UUID | None = None
    source_stage: str | None = None
    source_year: int | None = None
    source_problem_number: str | None = None


class CreateTaskResponse(BaseModel):
    id: uuid.UUID


class UpdateTaskRequest(BaseModel):
    title: str | None = None
    statement: str | None = None
    answer: str | None = None
    difficulty: int | None = Field(default=None, ge=1, le=10)
    subject: Literal["math", "physics"] | None = None
    grade: int | None = None
    classifier: str | None = None
    problem_type: str | None = None
    status: str | None = None
    solution_method_id: uuid.UUID | None = None
    source_stage: str | None = None
    source_year: int | None = None
    source_problem_number: str | None = None


class SetDifficultyRequest(BaseModel):
    difficulty: int = Field(ge=1, le=10)


class SetDifficultyResponse(BaseModel):
    task_id: uuid.UUID
    difficulty: int


class EmbeddingQueuedResponse(BaseModel):
    status: Literal["queued"] = "queued"


class StaleEmbeddingItem(BaseModel):
    id: uuid.UUID
    embedding_model: str | None
    embedding_updated_at: datetime | None


class StaleEmbeddingsResponse(BaseModel):
    count: int
    items: list[StaleEmbeddingItem]


class CreateEntityResponse(BaseModel):
    id: uuid.UUID


class CreateTopicRequest(BaseModel):
    name: str = Field(min_length=1)
    parent_id: uuid.UUID | None = None


class UpdateTopicRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    parent_id: uuid.UUID | None = None


class CreateOlympiadRequest(BaseModel):
    name: str = Field(min_length=1)
    short_name: str = Field(min_length=1)


class UpdateOlympiadRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    short_name: str | None = Field(default=None, min_length=1)


class CreateSolutionMethodRequest(BaseModel):
    name: str = Field(min_length=1)
    parent_id: uuid.UUID | None = None


class UpdateSolutionMethodRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    parent_id: uuid.UUID | None = None
