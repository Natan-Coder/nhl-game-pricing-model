-- V21__fix_edges_constraints.sql
-- Re-add the constraint for moneyline edges (without line_number)
-- Keep the constraint for spread/total edges (with line_number)
-- Both are needed because moneylines don't have lines!

-- Add back the moneyline constraint if it doesn't exist
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'uq_edges_minute'
      AND conrelid = 'public.edges'::regclass
  ) THEN
    ALTER TABLE public.edges
      ADD CONSTRAINT uq_edges_minute
          UNIQUE (game_id, book, market, outcome, american_odds, computed_minute_utc);
    RAISE NOTICE 'Added uq_edges_minute constraint for moneylines';
  END IF;
END $$;

-- Verify both constraints exist
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'uq_edges_minute_with_line'
      AND conrelid = 'public.edges'::regclass
  ) THEN
    RAISE EXCEPTION 'Missing uq_edges_minute_with_line constraint!';
  END IF;

  RAISE NOTICE 'Both constraints verified: uq_edges_minute (moneylines) and uq_edges_minute_with_line (spreads/totals)';
END $$;