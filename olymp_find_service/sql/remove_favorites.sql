-- Apply once to an existing olymp-db after retiring the favorites feature.
-- This removes saved favorites; catalog tables and their rows are unchanged.
DROP TABLE IF EXISTS favorite;
