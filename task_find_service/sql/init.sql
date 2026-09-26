CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE solution_methods (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    parent_id UUID REFERENCES solution_methods (id) ON DELETE SET NULL,
    path TEXT NOT NULL,
    depth SMALLINT NOT NULL DEFAULT 0,
    embedding vector(1024),
    embedding_model TEXT,
    embedding_model_version TEXT,
    CONSTRAINT solution_methods_parent_name_unique UNIQUE (parent_id, name),
    CONSTRAINT solution_methods_embedding_meta_check CHECK (
        embedding IS NULL
        OR (embedding_model IS NOT NULL AND embedding_model_version IS NOT NULL)
    )
);

CREATE INDEX solution_methods_parent_id_idx ON solution_methods (parent_id);
CREATE INDEX solution_methods_path_idx ON solution_methods (path);

CREATE TABLE topics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    parent_id UUID REFERENCES topics (id) ON DELETE SET NULL,
    path TEXT NOT NULL,
    depth SMALLINT NOT NULL DEFAULT 0,
    embedding vector(1024),
    embedding_model TEXT,
    embedding_model_version TEXT,
    CONSTRAINT topics_parent_name_unique UNIQUE (parent_id, name),
    CONSTRAINT topics_embedding_meta_check CHECK (
        embedding IS NULL
        OR (embedding_model IS NOT NULL AND embedding_model_version IS NOT NULL)
    )
);

CREATE INDEX topics_parent_id_idx ON topics (parent_id);
CREATE INDEX topics_path_idx ON topics (path);
CREATE INDEX topics_depth_idx ON topics (depth);

CREATE TABLE olympiads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    short_name TEXT,
    embedding vector(1024),
    embedding_model TEXT,
    embedding_model_version TEXT,
    CONSTRAINT olympiads_embedding_meta_check CHECK (
        embedding IS NULL
        OR (embedding_model IS NOT NULL AND embedding_model_version IS NOT NULL)
    )
);

CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT,
    statement TEXT NOT NULL,
    answer TEXT,
    subject TEXT CHECK (subject IN ('math', 'physics')),
    grade SMALLINT,
    problem_type TEXT,
    classifier TEXT,
    difficulty SMALLINT CHECK (difficulty BETWEEN 1 AND 10),
    solution_method_id UUID REFERENCES solution_methods (id) ON DELETE SET NULL,
    olympiad_id UUID REFERENCES olympiads (id) ON DELETE SET NULL,
    source_stage TEXT,
    source_year SMALLINT,
    source_problem_number TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
    topic_search_vector tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('russian', coalesce(classifier, '')), 'A')
        || setweight(to_tsvector('russian', coalesce(title, '')), 'A')
        || setweight(to_tsvector('russian', coalesce(statement, '')), 'B')
    ) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT tasks_statement_status_check CHECK (status <> 'published' OR btrim(statement) <> '')
);

CREATE INDEX tasks_topic_search_vector_gin_idx ON tasks USING gin (topic_search_vector);
CREATE INDEX tasks_difficulty_idx ON tasks (difficulty);
CREATE INDEX tasks_status_idx ON tasks (status);
CREATE INDEX tasks_subject_grade_year_idx ON tasks (subject, grade, source_year);
CREATE INDEX tasks_solution_method_id_idx ON tasks (solution_method_id);
CREATE INDEX tasks_olympiad_id_idx ON tasks (olympiad_id);

CREATE TABLE task_sources (
    task_id UUID NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
    source_system TEXT NOT NULL,
    subject TEXT NOT NULL,
    external_id TEXT NOT NULL,
    url TEXT,
    scraped_at TIMESTAMPTZ,
    PRIMARY KEY (source_system, subject, external_id),
    UNIQUE (task_id, source_system)
);
CREATE INDEX task_sources_task_id_idx ON task_sources (task_id);

CREATE TABLE task_embeddings (
    task_id UUID NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('topic', 'solution')),
    model TEXT NOT NULL,
    dimensions INTEGER NOT NULL CHECK (dimensions = 2560),
    text_hash TEXT NOT NULL,
    embedding vector(2560) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (task_id, kind, model, dimensions)
);
CREATE INDEX task_embeddings_topic_hnsw_idx ON task_embeddings
    USING hnsw ((embedding::halfvec(2560)) halfvec_cosine_ops)
    WHERE kind = 'topic' AND model = 'qwen/qwen3-embedding-4b' AND dimensions = 2560;
CREATE INDEX task_embeddings_solution_hnsw_idx ON task_embeddings
    USING hnsw ((embedding::halfvec(2560)) halfvec_cosine_ops)
    WHERE kind = 'solution' AND model = 'qwen/qwen3-embedding-4b' AND dimensions = 2560;

CREATE TABLE task_topics (
    task_id UUID NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
    topic_id UUID NOT NULL REFERENCES topics (id) ON DELETE CASCADE,
    weight REAL NOT NULL DEFAULT 1.0,
    PRIMARY KEY (task_id, topic_id)
);

CREATE TABLE solutions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    author TEXT,
    is_generated BOOLEAN NOT NULL DEFAULT false,
    is_verified BOOLEAN NOT NULL DEFAULT false,
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('russian', content)
    ) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX solutions_task_id_idx ON solutions (task_id);
CREATE INDEX solutions_search_vector_gin_idx ON solutions USING gin (search_vector);

CREATE TABLE hints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
    level SMALLINT NOT NULL,
    content TEXT NOT NULL,
    is_verified BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (task_id, level)
);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tasks_updated_at
    BEFORE UPDATE ON tasks
    FOR EACH ROW
    EXECUTE PROCEDURE set_updated_at();
