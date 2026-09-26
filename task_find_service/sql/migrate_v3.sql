-- Convert task-to-olympiad from a join table to a nullable direct foreign key.
-- If legacy data links a task to multiple olympiads, keep the smallest UUID.
BEGIN;

ALTER TABLE tasks ADD COLUMN olympiad_id UUID REFERENCES olympiads(id) ON DELETE SET NULL;

UPDATE tasks t
SET olympiad_id = chosen.olympiad_id
FROM (
    SELECT DISTINCT ON (task_id) task_id, olympiad_id
    FROM task_olympiads
    ORDER BY task_id, olympiad_id
) AS chosen
WHERE chosen.task_id = t.id;

DROP TABLE task_olympiads;
CREATE INDEX tasks_olympiad_id_idx ON tasks (olympiad_id);

COMMIT;
