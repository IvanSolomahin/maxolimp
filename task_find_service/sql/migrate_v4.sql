-- Merge olympiad records that differ only by source-added grade lists or typography.
-- Task references are moved before duplicate records are removed.
BEGIN;

CREATE TEMP TABLE olympiad_merge_map ON COMMIT DROP AS
WITH normalized AS (
    SELECT
        o.id,
        o.name,
        COUNT(t.id) AS task_count,
        btrim(regexp_replace(
            replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(
                lower(o.name), '—', '-'), '–', '-'), '−', '-'), '/', ' '),
                '«', ''), '»', ''), '„', ''), '“', ''), '”', ''), '’', ''''), '‘', ''''),
            '\s*,\s*(\d{1,2}\s*,\s*)*\d{1,2}\s*$', '', 'g'
        )) AS merge_key,
        o.name !~ '\s*,\s*(\d{1,2}\s*,\s*)*\d{1,2}\s*$' AS has_base_name
    FROM olympiads o
    LEFT JOIN tasks t ON t.olympiad_id = o.id
    GROUP BY o.id, o.name
), cleaned AS (
    SELECT *, btrim(regexp_replace(merge_key, '\s+', ' ', 'g')) AS normalized_key
    FROM normalized
), ranked AS (
    SELECT *,
        COUNT(*) OVER (PARTITION BY normalized_key) AS group_size,
        ROW_NUMBER() OVER (
            PARTITION BY normalized_key
            ORDER BY has_base_name DESC, task_count DESC, name
        ) AS preference
    FROM cleaned
), winners AS (
    SELECT id, normalized_key,
        btrim(regexp_replace(name, '\s*,\s*(\d{1,2}\s*,\s*)*\d{1,2}\s*$', '', 'g')) AS canonical_name
    FROM ranked
    WHERE preference = 1
)
SELECT r.id AS old_id, w.id AS canonical_id, w.canonical_name
FROM ranked r
JOIN winners w USING (normalized_key)
WHERE r.group_size > 1;

UPDATE tasks t
SET olympiad_id = m.canonical_id
FROM olympiad_merge_map m
WHERE t.olympiad_id = m.old_id
  AND m.old_id <> m.canonical_id;

DELETE FROM olympiads o
USING olympiad_merge_map m
WHERE o.id = m.old_id
  AND m.old_id <> m.canonical_id;

UPDATE olympiads o
SET name = m.canonical_name
FROM olympiad_merge_map m
WHERE o.id = m.canonical_id
  AND o.name IS DISTINCT FROM m.canonical_name;

COMMIT;
