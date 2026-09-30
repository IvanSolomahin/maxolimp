-- Upgrade an existing catalog without replacing its rows.
-- The retired favorites table is removed; catalog rows are preserved.
BEGIN;

DROP TABLE IF EXISTS favorite;

ALTER TABLE subject_olympiad DROP CONSTRAINT subject_olympiad_pkey;
ALTER TABLE subject_olympiad ADD COLUMN id SERIAL PRIMARY KEY;
ALTER TABLE subject_olympiad
    ADD CONSTRAINT subject_olympiad_subject_id_olympiad_id_key
    UNIQUE (subject_id, olympiad_id);

COMMIT;
