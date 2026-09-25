CREATE TABLE university (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE city (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE universities_cities (
    university_id INTEGER NOT NULL REFERENCES university (id) ON DELETE CASCADE,
    city_id INTEGER NOT NULL REFERENCES city (id) ON DELETE CASCADE,
    PRIMARY KEY (university_id, city_id)
);

CREATE TABLE program (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE
);

CREATE TABLE programs_universities (
    program_id INTEGER NOT NULL REFERENCES program (id) ON DELETE CASCADE,
    university_id INTEGER NOT NULL REFERENCES university (id) ON DELETE CASCADE,
    PRIMARY KEY (program_id, university_id)
);

CREATE TABLE subject (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE olympiad (
    id SERIAL PRIMARY KEY,
    host_university_id INTEGER NOT NULL REFERENCES university (id) ON DELETE RESTRICT,
    name TEXT NOT NULL UNIQUE,
    complexity INTEGER NOT NULL,
    description TEXT NOT NULL
);

CREATE TABLE subject_olympiad (
    subject_id INTEGER NOT NULL REFERENCES subject (id) ON DELETE CASCADE,
    olympiad_id INTEGER NOT NULL REFERENCES olympiad (id) ON DELETE CASCADE,
    PRIMARY KEY (subject_id, olympiad_id)
);

CREATE TABLE stage (
    stage_id SERIAL PRIMARY KEY,
    olymp_id INTEGER NOT NULL REFERENCES olympiad (id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    is_online BOOLEAN NOT NULL DEFAULT false,
    location TEXT,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL
);

CREATE INDEX stage_olymp_id_idx ON stage (olymp_id);

CREATE TABLE benefit (
    id SERIAL PRIMARY KEY,
    olympiad_id INTEGER NOT NULL REFERENCES olympiad (id) ON DELETE CASCADE,
    program_id INTEGER NOT NULL REFERENCES program (id) ON DELETE CASCADE,
    university_id INTEGER NOT NULL REFERENCES university (id) ON DELETE CASCADE,
    benefit_type TEXT NOT NULL CHECK (
        benefit_type IN ('no entrance exams', '100 points', 'additional_points')
    )
);

CREATE INDEX benefit_olympiad_id_idx ON benefit (olympiad_id);
CREATE INDEX benefit_university_program_idx ON benefit (university_id, program_id);

CREATE TABLE favorite (
    user_id INTEGER NOT NULL,
    olympiad_id INTEGER NOT NULL REFERENCES olympiad (id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, olympiad_id)
);

INSERT INTO university (id, name) VALUES
    (1, 'НИУ ВШЭ'),
    (2, 'МГУ имени М. В. Ломоносова');

INSERT INTO city (id, name) VALUES
    (1, 'Москва'),
    (2, 'Санкт-Петербург'),
    (3, 'Нижний Новгород'),
    (4, 'Пермь');

INSERT INTO universities_cities (university_id, city_id) VALUES
    (1, 1), (1, 2), (1, 3), (1, 4),
    (2, 1);

INSERT INTO program (id, name, code) VALUES
    (12, 'Прикладная математика и информатика', '01.03.02'),
    (13, 'Компьютерные науки и анализ данных', '02.03.01'),
    (14, 'Математика', '01.03.01');

INSERT INTO programs_universities (program_id, university_id) VALUES
    (12, 1), (13, 1), (14, 1), (14, 2);

INSERT INTO subject (id, name) VALUES
    (1, 'Математика'),
    (2, 'Информатика');

INSERT INTO olympiad (id, host_university_id, name, complexity, description) VALUES
    (1, 1, 'Высшая проба', 4, 'Межвузовская олимпиада школьников'),
    (2, 2, 'Ломоносов', 5, 'Олимпиада МГУ');

INSERT INTO subject_olympiad (subject_id, olympiad_id) VALUES
    (1, 1), (2, 1), (1, 2);

INSERT INTO stage (stage_id, olymp_id, name, is_online, location, start_date, end_date) VALUES
    (10, 1, 'Отборочный этап', true, NULL, '2026-01-10 10:00:00', '2026-02-10 23:59:59'),
    (11, 1, 'Заключительный этап', false, 'Москва', '2026-03-15 10:00:00', '2026-03-15 14:00:00'),
    (12, 2, 'Отборочный этап', true, NULL, '2026-01-15 10:00:00', '2026-02-20 23:59:59');

INSERT INTO benefit (id, olympiad_id, program_id, university_id, benefit_type) VALUES
    (101, 1, 12, 1, 'no entrance exams'),
    (102, 1, 13, 1, '100 points'),
    (103, 2, 14, 2, 'additional_points');

SELECT setval('university_id_seq', (SELECT MAX(id) FROM university));
SELECT setval('city_id_seq', (SELECT MAX(id) FROM city));
SELECT setval('program_id_seq', (SELECT MAX(id) FROM program));
SELECT setval('subject_id_seq', (SELECT MAX(id) FROM subject));
SELECT setval('olympiad_id_seq', (SELECT MAX(id) FROM olympiad));
SELECT setval('stage_stage_id_seq', (SELECT MAX(stage_id) FROM stage));
SELECT setval('benefit_id_seq', (SELECT MAX(id) FROM benefit));
