-- Remove data created by the old placeholder generators. Imported solutions remain.
-- Safe to run again after a completed transaction.
BEGIN;

DO $$
DECLARE
    generated_count bigint;
    hint_count bigint;
BEGIN
    IF to_regclass('public.hints') IS NOT NULL THEN
        EXECUTE 'SELECT count(*) FROM public.hints' INTO hint_count;
        RAISE NOTICE 'Deleting % placeholder hints', hint_count;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'solutions'
          AND column_name = 'is_generated'
    ) THEN
        EXECUTE 'SELECT count(*) FROM public.solutions WHERE is_generated' INTO generated_count;
        RAISE NOTICE 'Deleting % generated solutions', generated_count;
        EXECUTE 'DELETE FROM public.solutions WHERE is_generated';
    END IF;
END $$;

DROP TABLE IF EXISTS public.hints;
ALTER TABLE IF EXISTS public.solutions DROP COLUMN IF EXISTS is_generated;

COMMIT;
