-- Apply once to an existing v1 PostgreSQL database before running import_etl.py.
-- Old columns and their data are retained, but v2 code uses the new tables.
BEGIN;

ALTER TABLE olympiads ALTER COLUMN short_name DROP NOT NULL;
ALTER TABLE tasks ALTER COLUMN title DROP NOT NULL;
ALTER TABLE tasks ALTER COLUMN difficulty DROP NOT NULL;
ALTER TABLE tasks ADD COLUMN subject TEXT CHECK (subject IN ('math', 'physics'));
ALTER TABLE tasks ADD COLUMN grade SMALLINT;
ALTER TABLE tasks ADD COLUMN problem_type TEXT;
ALTER TABLE tasks ADD COLUMN classifier TEXT;
ALTER TABLE tasks ADD COLUMN topic_search_vector tsvector GENERATED ALWAYS AS (
    setweight(to_tsvector('russian', coalesce(classifier, '')), 'A')
    || setweight(to_tsvector('russian', coalesce(title, '')), 'A')
    || setweight(to_tsvector('russian', coalesce(statement, '')), 'B')
) STORED;
ALTER TABLE tasks ADD CONSTRAINT tasks_statement_status_check
    CHECK (status <> 'published' OR btrim(statement) <> '') NOT VALID;
CREATE INDEX tasks_topic_search_vector_gin_idx ON tasks USING gin (topic_search_vector);
CREATE INDEX tasks_subject_grade_year_idx ON tasks (subject, grade, source_year);

CREATE TABLE task_sources (
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
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
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
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

ALTER TABLE solutions ADD COLUMN search_vector tsvector GENERATED ALWAYS AS (
    to_tsvector('russian', content)
) STORED;
CREATE INDEX solutions_search_vector_gin_idx ON solutions USING gin (search_vector);

COMMIT;
