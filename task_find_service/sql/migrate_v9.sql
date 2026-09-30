BEGIN;

CREATE TABLE IF NOT EXISTS classifier_tags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE CHECK (btrim(name) <> '')
);
CREATE TABLE IF NOT EXISTS task_classifier_tags (
    task_id UUID NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
    tag_id UUID NOT NULL REFERENCES classifier_tags (id) ON DELETE CASCADE,
    PRIMARY KEY (task_id, tag_id)
);
CREATE INDEX IF NOT EXISTS task_classifier_tags_tag_id_idx ON task_classifier_tags (tag_id, task_id);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'tasks' AND column_name = 'classifier') THEN
        INSERT INTO classifier_tags (name)
        SELECT DISTINCT btrim(parts.name)
        FROM tasks t CROSS JOIN LATERAL unnest(string_to_array(coalesce(t.classifier, ''), ' , ')) AS parts(name)
        WHERE btrim(parts.name) <> ''
        ON CONFLICT (name) DO NOTHING;

        INSERT INTO task_classifier_tags (task_id, tag_id)
        SELECT DISTINCT t.id, tag.id
        FROM tasks t
        CROSS JOIN LATERAL unnest(string_to_array(coalesce(t.classifier, ''), ' , ')) AS parts(name)
        JOIN classifier_tags tag ON tag.name = btrim(parts.name)
        ON CONFLICT DO NOTHING;

        ALTER TABLE tasks DROP COLUMN topic_search_vector;
        ALTER TABLE tasks DROP COLUMN classifier;
        ALTER TABLE tasks ADD COLUMN topic_search_vector tsvector GENERATED ALWAYS AS (
            setweight(to_tsvector('russian', coalesce(title, '')), 'A')
            || setweight(to_tsvector('russian', coalesce(statement, '')), 'B')
        ) STORED;
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS tasks_topic_search_vector_gin_idx ON tasks USING gin (topic_search_vector);

COMMIT;
