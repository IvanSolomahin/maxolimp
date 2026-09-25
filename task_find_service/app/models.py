import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Float,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SolutionMethod(Base):
    __tablename__ = "solution_methods"
    __table_args__ = (
        UniqueConstraint("parent_id", "name", name="solution_methods_parent_name_unique"),
        CheckConstraint(
            "embedding IS NULL OR (embedding_model IS NOT NULL AND embedding_model_version IS NOT NULL)",
            name="solution_methods_embedding_meta_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("solution_methods.id", ondelete="SET NULL")
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    depth: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    embedding = mapped_column(Vector(1024), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(Text)
    embedding_model_version: Mapped[str | None] = mapped_column(Text)


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint("parent_id", "name", name="topics_parent_name_unique"),
        CheckConstraint(
            "embedding IS NULL OR (embedding_model IS NOT NULL AND embedding_model_version IS NOT NULL)",
            name="topics_embedding_meta_check",
        ),
        Index("topics_parent_id_idx", "parent_id"),
        Index("topics_path_idx", "path"),
        Index("topics_depth_idx", "depth"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id", ondelete="SET NULL")
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    depth: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    embedding = mapped_column(Vector(1024), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(Text)
    embedding_model_version: Mapped[str | None] = mapped_column(Text)


class Olympiad(Base):
    __tablename__ = "olympiads"
    __table_args__ = (
        CheckConstraint(
            "embedding IS NULL OR (embedding_model IS NOT NULL AND embedding_model_version IS NOT NULL)",
            name="olympiads_embedding_meta_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    short_name: Mapped[str | None] = mapped_column(Text)
    embedding = mapped_column(Vector(1024), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(Text)
    embedding_model_version: Mapped[str | None] = mapped_column(Text)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("difficulty BETWEEN 1 AND 10", name="tasks_difficulty_check"),
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="tasks_status_check",
        ),
        CheckConstraint("status <> 'published' OR btrim(statement) <> ''", name="tasks_statement_status_check"),
        Index("tasks_difficulty_idx", "difficulty"),
        Index("tasks_status_idx", "status"),
        Index("tasks_subject_grade_year_idx", "subject", "grade", "source_year"),
        Index("tasks_solution_method_id_idx", "solution_method_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str | None] = mapped_column(Text)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(Text)
    grade: Mapped[int | None] = mapped_column(SmallInteger)
    problem_type: Mapped[str | None] = mapped_column(Text)
    classifier: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[int | None] = mapped_column(SmallInteger)
    solution_method_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("solution_methods.id", ondelete="SET NULL")
    )
    source_stage: Mapped[str | None] = mapped_column(Text)
    source_year: Mapped[int | None] = mapped_column(SmallInteger)
    source_problem_number: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    topic_search_vector = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('russian', coalesce(classifier, '')), 'A') "
            "|| setweight(to_tsvector('russian', coalesce(title, '')), 'A') "
            "|| setweight(to_tsvector('russian', coalesce(statement, '')), 'B')",
            persisted=True,
        ),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    solution_method: Mapped[SolutionMethod | None] = relationship("SolutionMethod")
    task_topics: Mapped[list["TaskTopic"]] = relationship("TaskTopic", back_populates="task")
    task_olympiads: Mapped[list["TaskOlympiad"]] = relationship("TaskOlympiad", back_populates="task")
    solutions: Mapped[list["Solution"]] = relationship("Solution", back_populates="task")
    hints: Mapped[list["Hint"]] = relationship("Hint", back_populates="task")
    sources: Mapped[list["TaskSource"]] = relationship("TaskSource", back_populates="task")
    embeddings: Mapped[list["TaskEmbedding"]] = relationship("TaskEmbedding", back_populates="task")


class TaskSource(Base):
    __tablename__ = "task_sources"
    __table_args__ = (UniqueConstraint("task_id", "source_system"),)

    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    source_system: Mapped[str] = mapped_column(Text, primary_key=True)
    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    external_id: Mapped[str] = mapped_column(Text, primary_key=True)
    url: Mapped[str | None] = mapped_column(Text)
    scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    task: Mapped[Task] = relationship("Task", back_populates="sources")


class TaskEmbedding(Base):
    __tablename__ = "task_embeddings"
    __table_args__ = (CheckConstraint("kind IN ('topic', 'solution')"), CheckConstraint("dimensions = 2560"),)

    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    kind: Mapped[str] = mapped_column(Text, primary_key=True)
    model: Mapped[str] = mapped_column(Text, primary_key=True)
    dimensions: Mapped[int] = mapped_column(Integer, primary_key=True)
    text_hash: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(2560), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    task: Mapped[Task] = relationship("Task", back_populates="embeddings")


class TaskTopic(Base):
    __tablename__ = "task_topics"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    task: Mapped[Task] = relationship("Task", back_populates="task_topics")
    topic: Mapped[Topic] = relationship("Topic")


class TaskOlympiad(Base):
    __tablename__ = "task_olympiads"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    olympiad_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("olympiads.id", ondelete="CASCADE"), primary_key=True
    )

    task: Mapped[Task] = relationship("Task", back_populates="task_olympiads")
    olympiad: Mapped[Olympiad] = relationship("Olympiad")


class Solution(Base):
    __tablename__ = "solutions"
    __table_args__ = (Index("solutions_task_id_idx", "task_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(Text)
    is_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    search_vector = mapped_column(TSVECTOR, Computed("to_tsvector('russian', content)", persisted=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task: Mapped[Task] = relationship("Task", back_populates="solutions")


class Hint(Base):
    __tablename__ = "hints"
    __table_args__ = (UniqueConstraint("task_id", "level", name="hints_task_level_unique"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task: Mapped[Task] = relationship("Task", back_populates="hints")
