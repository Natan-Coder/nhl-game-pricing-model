-- V20__drop_old_edges_constraint.sql
-- Drop the old constraint that doesn't include line_number
-- Keep the newer uq_edges_minute_with_line constraint

DO $$
BEGIN
    IF EXISTS (
      SELECT 1
      FROM pg_constraint
      WHERE conname = 'uq_edges_minute'
        AND conrelid = 'public.edges'::regclass
    ) THEN
      ALTER TABLE public.edges DROP CONSTRAINT uq_edges_minute;
      RAISE NOTICE 'Dropped old uq_edges_minute constraint';
    END IF;
END $$;