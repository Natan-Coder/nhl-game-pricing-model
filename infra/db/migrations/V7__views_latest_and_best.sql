-- Latest quote per (game, book, market, outcome, line_number), by captured_a
CREATE OR REPLACE VIEW v_latest_quotes AS
WITH ranked AS (
  SELECT
    q.*,
    ROW_NUMBER() OVER (
       PARTITION BY q.game_id, q.book, q.market, q.outcome, COALESCE(q.line_number, -1)
       ORDER BY q.captured_at DESC
    ) AS rn
  FROM odds_quotes q
)
SELECT
  game_id, book, market, outcome, american_odds, line_number, captured_at
FROM ranked
WHERE rn = 1;

-- "Best" moneyline across books for each (game_id, outcome)
-- Higher american_odds is better for bettor (e.g., +115 > +105, -105 > -120 because -105 is larger)
DROP MATERIALIZED VIEW IF EXISTS mv_best_moneyline;
CREATE MATERIALIZED VIEW mv_best_moneyline AS
SELECT DISTINCT ON (lq.game_id, lq.outcome)
  lq.game_id,
  lq.outcome,
  lq.book,
  lq.american_odds,
  lq.captured_at
FROM v_latest_quotes lq
WHERE lq.market = 'moneyline'
ORDER BY lq.game_id, lq.outcome, lq.american_odds DESC, lq.captured_at DESC;

-- Helpful index for fast lookups/refresh
CREATE INDEX IF NOT EXISTS ix_mv_best_moneyline_game ON mv_best_moneyline (game_id, outcome);

-- Optional helper:  refresh concurrently in the future if you like
-- To use CONCURRENTLY you need a unique index on the MV; for now a normal refresh is fine.