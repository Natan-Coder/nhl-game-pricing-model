-- V5__perf_indexes.sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_quotes_game ON odds_quotes (game_id, market, outcome, captured_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_edges_game ON edges (game_id, computed_at DESC);
