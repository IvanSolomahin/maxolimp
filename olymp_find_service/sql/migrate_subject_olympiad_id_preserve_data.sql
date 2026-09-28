-- Upgrade an existing catalog without replacing its rows.
-- The old favorite key points to olympiad.id, while the new key points to a
-- subject/olympiad pair. An existing favorite cannot be mapped unambiguously.
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM favorite LIMIT 1) THEN
        RAISE EXCEPTION 'Cannot migrate nonempty favorite table automatically';
    END IF;
END $$;

ALTER TABLE subject_olympiad DROP CONSTRAINT subject_olympiad_pkey;
ALTER TABLE subject_olympiad ADD COLUMN id SERIAL PRIMARY KEY;
ALTER TABLE subject_olympiad
    ADD CONSTRAINT subject_olympiad_subject_id_olympiad_id_key
    UNIQUE (subject_id, olympiad_id);

ALTER TABLE favorite DROP CONSTRAINT favorite_olympiad_id_fkey;
ALTER TABLE favorite
    ADD CONSTRAINT favorite_olympiad_id_fkey
    FOREIGN KEY (olympiad_id) REFERENCES subject_olympiad (id) ON DELETE CASCADE;

COMMIT;
