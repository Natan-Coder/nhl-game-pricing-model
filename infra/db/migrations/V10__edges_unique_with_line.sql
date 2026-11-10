-- Add line_number to edges (scaled integer like odds_quotes; nullable for moneyline)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'edges'
      AND column_name  = 'line_number'
  ) THEN
ALTER TABLE public.edges
    ADD COLUMN line_number integer;
END IF;
END$$;

-- Add a unique constraint that includes line_number + minute bucket
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'uq_edges_minute_with_line'
      AND conrelid = 'public.edges'::regclass
  ) THEN
ALTER TABLE public.edges
    ADD CONSTRAINT uq_edges_minute_with_line
        UNIQUE (game_id, book, market, outcome, american_odds, line_number, computed_minute_utc);
END IF;
END$$;
