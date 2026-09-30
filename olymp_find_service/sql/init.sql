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
    name TEXT,
    code TEXT UNIQUE
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
    host_university_id INTEGER REFERENCES university (id) ON DELETE RESTRICT,
    name TEXT NOT NULL UNIQUE,
    complexity INTEGER,
    description TEXT
);

CREATE TABLE subject_olympiad (
    id SERIAL PRIMARY KEY,
    subject_id INTEGER NOT NULL REFERENCES subject (id) ON DELETE CASCADE,
    olympiad_id INTEGER NOT NULL REFERENCES olympiad (id) ON DELETE CASCADE,
    UNIQUE (subject_id, olympiad_id)
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
