-- Ensure these columns auto-populate in every environment
ALTER TABLE game_pricing
    ALTER COLUMN created_at SET DEFAULT now();

ALTER TABLE odds_quotes
    ALTER COLUMN captured_at SET DEFAULT now();

-- Ensure auto timestamps & performance.
ALTER TABLE edges
    ALTER COLUMN computed_at SET DEFAULT now();

-- Flyway: noTransaction
-- Use CONCURRENTLY outside transactions (Flyway will run this migration with no tx)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_quotes_game_latest
    ON odds_quotes (game_id, market, outcome, captured_at DESC);

-- Flyway: noTransaction
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_edges_game_time
    ON edges (game_id, computed_at DESC);