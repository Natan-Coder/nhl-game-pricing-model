-- Flyway: noTransaction
-- Use a UNIQUE INDEX with an expression instead of a table constraint.
-- If line_number is NULL we normalize it to -1 so one “tick” per book/market/outcome is unique.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_odds_quote_tick
  ON odds_quotes (
    game_id,
    book,
    market,
    outcome,
    captured_at,
    (COALESCE(line_number, -1))  -- if your column is NUMERIC instead of INT, use (-1)::numeric
  );