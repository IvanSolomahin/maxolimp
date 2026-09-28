-- Add the 25 subject links confirmed by olympiad descriptions in the workbook.
-- Safe to rerun on an existing catalog; no rows are removed or replaced.
BEGIN;

INSERT INTO subject_olympiad (subject_id, olympiad_id) VALUES
    (233, 73),
    (233, 74),
    (233, 83),
    (101, 85),
    (105, 90),
    (10, 92),
    (10, 93),
    (7, 100),
    (17, 102),
    (6, 103),
    (7, 103),
    (8, 103),
    (9, 103),
    (14, 103),
    (115, 103),
    (232, 103),
    (248, 103),
    (7, 107),
    (18, 107),
    (5, 113),
    (7, 113),
    (48, 113),
    (2, 115),
    (10, 116),
    (17, 119)
ON CONFLICT (subject_id, olympiad_id) DO NOTHING;

COMMIT;
