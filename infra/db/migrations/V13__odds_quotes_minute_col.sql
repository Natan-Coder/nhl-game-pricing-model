-- V13__odds_quotes_minute_col.sql
-- Make captured_minute_utc and line_key real columns and build a column-based unique index.

DO $$
BEGIN
  -- 1) Columns
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='odds_quotes' AND column_name='captured_minute_utc'
  ) THEN
ALTER TABLE public.odds_quotes
    ADD COLUMN captured_minute_utc timestamptz;
END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='odds_quotes' AND column_name='line_key'
  ) THEN
ALTER TABLE public.odds_quotes
    ADD COLUMN line_key integer;
END IF;
END$$;

-- 2) Backfill existing rows
UPDATE public.odds_quotes
SET
    captured_minute_utc = date_trunc('minute', captured_at),
    line_key = COALESCE(line_number, -1)
WHERE captured_minute_utc IS NULL OR line_key IS NULL;

-- 3) Trigger function to keep them set on insert/update
CREATE OR REPLACE FUNCTION public.set_odds_quotes_minute_linekey()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.captured_minute_utc := date_trunc('minute', NEW.captured_at);
  NEW.line_key := COALESCE(NEW.line_number, -1);
RETURN NEW;
END$$;

-- 4) (Re)create BEFORE triggers
DROP TRIGGER IF EXISTS trg_odds_quotes_minute_linekey_i ON public.odds_quotes;
CREATE TRIGGER trg_odds_quotes_minute_linekey_i
    BEFORE INSERT ON public.odds_quotes
    FOR EACH ROW EXECUTE FUNCTION public.set_odds_quotes_minute_linekey();

DROP TRIGGER IF EXISTS trg_odds_quotes_minute_linekey_u ON public.odds_quotes;
CREATE TRIGGER trg_odds_quotes_minute_linekey_u
    BEFORE UPDATE OF captured_at, line_number ON public.odds_quotes
    FOR EACH ROW EXECUTE FUNCTION public.set_odds_quotes_minute_linekey();

-- 5) Drop any old expression-based unique index if it exists
DO $$
DECLARE idx text;
BEGIN
SELECT indexname
INTO idx
FROM pg_indexes
WHERE schemaname='public'
  AND tablename='odds_quotes'
  AND indexdef ILIKE '%UNIQUE INDEX%'
    AND indexdef ILIKE '%date_trunc(''minute'', captured_at)%';
IF idx IS NOT NULL THEN
    EXECUTE format('DROP INDEX IF EXISTS public.%I', idx);
END IF;
END$$;

-- 6) Create the column-based unique index
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND tablename='odds_quotes' AND indexname='ux_odds_quotes_minute_linekey'
  ) THEN
CREATE UNIQUE INDEX ux_odds_quotes_minute_linekey
    ON public.odds_quotes (game_id, book, market, outcome, captured_minute_utc, line_key);
END IF;
END$$;
