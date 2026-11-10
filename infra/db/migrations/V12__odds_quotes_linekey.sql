-- V12__odds_quotes_linekey.sql
-- Make odds_quotes upsert-tolerant per minute+line_number using an IMMUTABLE wrapper.

-- 1) Drop any previous attempt indexes (safe if absent)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='ux_odds_quotes_minute') THEN
    EXECUTE 'DROP INDEX public.ux_odds_quotes_minute';
END IF;

  IF EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='ux_odds_quotes_minute_with_line') THEN
    EXECUTE 'DROP INDEX public.ux_odds_quotes_minute_with_line';
END IF;

  IF EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='ux_odds_quotes_minute_with_line_expr') THEN
    EXECUTE 'DROP INDEX public.ux_odds_quotes_minute_with_line_expr';
END IF;
END$$;

-- 2) Create an IMMUTABLE wrapper for minute truncation
CREATE OR REPLACE FUNCTION public.trunc_minute_utc(ts timestamptz)
RETURNS timestamptz
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
SELECT date_trunc('minute', ts)
           $$;

COMMENT ON FUNCTION public.trunc_minute_utc(timestamptz)
IS 'Immutable wrapper around date_trunc(''minute'', ts) for use in indexes and upserts.';

-- 3) Functional unique index that matches Python''s ON CONFLICT target
CREATE UNIQUE INDEX ux_odds_quotes_minute_with_line_expr
    ON public.odds_quotes (
                           game_id,
                           book,
                           market,
                           outcome,
                           american_odds,
        (COALESCE(line_number, -1)),
                           public.trunc_minute_utc(captured_at)
        );

COMMENT ON INDEX public.ux_odds_quotes_minute_with_line_expr IS
  'One odds quote per (game, book, market, outcome, american, line_number, minute).';
