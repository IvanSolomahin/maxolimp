-- Run together with seed.sql in one transaction when replacing the existing catalog.
BEGIN;
TRUNCATE favorite, benefit, stage, subject_olympiad, olympiad, subject, programs_universities, program, universities_cities, city, university RESTART IDENTITY CASCADE;
ALTER TABLE program ALTER COLUMN name DROP NOT NULL;
ALTER TABLE program ALTER COLUMN code DROP NOT NULL;
ALTER TABLE olympiad ALTER COLUMN host_university_id DROP NOT NULL;
ALTER TABLE olympiad ALTER COLUMN complexity DROP NOT NULL;
ALTER TABLE olympiad ALTER COLUMN description DROP NOT NULL;
ALTER TABLE subject_olympiad DROP CONSTRAINT subject_olympiad_pkey;
ALTER TABLE subject_olympiad ADD COLUMN id SERIAL PRIMARY KEY;
ALTER TABLE subject_olympiad ADD CONSTRAINT subject_olympiad_subject_id_olympiad_id_key UNIQUE (subject_id, olympiad_id);
ALTER TABLE favorite DROP CONSTRAINT favorite_olympiad_id_fkey;
ALTER TABLE favorite ADD CONSTRAINT favorite_olympiad_id_fkey FOREIGN KEY (olympiad_id) REFERENCES subject_olympiad (id) ON DELETE CASCADE;
