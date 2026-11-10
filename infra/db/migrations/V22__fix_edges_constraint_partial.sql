-- V22: Fix edges constraints - make both constraints partial and non-overlapping
--
-- The problem: uq_edges_minute was preventing spreads/totals with different line
-- values from being inserted in the same minute. The solution is to make BOTH
-- constraints partial so they don't overlap:
-- - uq_edges_minute: Only for moneylines (line_number IS NULL)
-- - uq_edges_minute_with_line: Only for spreads/totals (line_number IS NOT NULL)

DO $$
BEGIN
  -- Drop the existing uq_edges_minute constraint
  IF EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'uq_edges_minute'
      AND conrelid = 'public.edges'::regclass
  ) THEN
    ALTER TABLE public.edges DROP CONSTRAINT uq_edges_minute;
    RAISE NOTICE 'Dropped uq_edges_minute constraint';
  END IF;

  -- Drop the existing uq_edges_minute_with_line constraint
  IF EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'uq_edges_minute_with_line'
      AND conrelid = 'public.edges'::regclass
  ) THEN
    ALTER TABLE public.edges DROP CONSTRAINT uq_edges_minute_with_line;
    RAISE NOTICE 'Dropped uq_edges_minute_with_line constraint';
  END IF;

  -- Create partial unique index for moneylines only (line_number IS NULL)
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE indexname = 'uq_edges_minute_moneylines'
  ) THEN
    CREATE UNIQUE INDEX uq_edges_minute_moneylines
      ON public.edges (game_id, book, market, outcome, american_odds, computed_minute_utc)
      WHERE line_number IS NULL;
    RAISE NOTICE 'Created partial unique index uq_edges_minute_moneylines for moneylines';
  END IF;

  -- Create partial unique index for spreads/totals only (line_number IS NOT NULL)
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE indexname = 'uq_edges_minute_with_line'
  ) THEN
    CREATE UNIQUE INDEX uq_edges_minute_with_line
      ON public.edges (game_id, book, market, outcome, american_odds, line_number, computed_minute_utc)
      WHERE line_number IS NOT NULL;
    RAISE NOTICE 'Created partial unique index uq_edges_minute_with_line for spreads/totals';
  END IF;
END $$;
