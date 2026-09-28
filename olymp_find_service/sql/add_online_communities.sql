CREATE TABLE IF NOT EXISTS online_communities (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    subject     TEXT NOT NULL,
    platform    TEXT NOT NULL,
    url         TEXT NOT NULL,
    description TEXT,
    sort_order  INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS online_communities_subject_idx
    ON online_communities (subject, sort_order, name);
