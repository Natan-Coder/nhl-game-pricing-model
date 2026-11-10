-- Make V8 transactional only (no CONCURRENTLY).

-- 1) Add column to store minute bucket in UTC (timestamp without time zone)
ALTER TABLE edges
    ADD COLUMN IF NOT EXISTS computed_minute_utc timestamp without time zone;

-- 2) Trigger function to set the minute bucket (truncate computed_at to minute in UTC)
CREATE OR REPLACE FUNCTION trg_set_edges_computed_minute()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.computed_minute_utc := date_trunc('minute', (NEW.computed_at AT TIME ZONE 'UTC'));
RETURN NEW;
END;
$$;

-- 3) Trigger on insert/update of computed_at
DROP TRIGGER IF EXISTS set_edges_computed_minute ON edges;
CREATE TRIGGER set_edges_computed_minute
    BEFORE INSERT OR UPDATE OF computed_at ON edges
    FOR EACH ROW
    EXECUTE FUNCTION trg_set_edges_computed_minute();

-- 4) Backfill any existing rows
UPDATE edges
SET computed_minute_utc = date_trunc('minute', (computed_at AT TIME ZONE 'UTC'))
WHERE computed_minute_utc IS NULL;

-- 5) Unique constraint (transactional) for idempotent upsert per minute
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
END IF;
END$$;
