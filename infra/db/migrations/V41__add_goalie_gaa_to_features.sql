-- V41: Add goalie GAA (Goals Against Average) columns to game_features
-- Enables Phase 2 model training with goalie performance features

-- Add GAA columns for starting goalies
ALTER TABLE game_features
ADD COLUMN IF NOT EXISTS home_goalie_gaa NUMERIC(4,2),
ADD COLUMN IF NOT EXISTS away_goalie_gaa NUMERIC(4,2);

-- ============================================================
-- Documentation Comments
-- ============================================================

COMMENT ON COLUMN game_features.home_goalie_gaa IS
'Home starting goalie''s GAA (Goals Against Average) as of this game date.
NULL when goalie data not available for historical games.
Updated by update_game_features_goalie_gaa.py ETL script.
Used for Phase 2 model training alongside ELO and rest days.';

COMMENT ON COLUMN game_features.away_goalie_gaa IS
'Away starting goalie''s GAA (Goals Against Average) as of this game date.
NULL when goalie data not available for historical games.
Updated by update_game_features_goalie_gaa.py ETL script.
Used for Phase 2 model training alongside ELO and rest days.';

-- ============================================================
-- Performance Index
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_game_features_goalie_gaa
ON game_features(game_id)
WHERE home_goalie_gaa IS NOT NULL AND away_goalie_gaa IS NOT NULL;

-- EXPLANATION:
-- This partial index optimizes queries that filter for games with goalie data.
--
-- Common queries:
--
-- Query 1: "Get all games with complete feature set for training"
--   SELECT * FROM game_features
--   WHERE home_elo IS NOT NULL
--     AND home_rest IS NOT NULL
--     AND home_goalie_gaa IS NOT NULL
--     AND away_goalie_gaa IS NOT NULL
--   → Partial index helps filter to games with goalie data
--
-- Query 2: "Count games ready for Phase 2 model training"
--   SELECT COUNT(*) FROM game_features
--   WHERE home_goalie_gaa IS NOT NULL
--   → Index scan instead of full table scan
--
-- WHY PARTIAL INDEX?
-- Not all games have goalie GAA data (historical games may be missing).
-- Partial index only stores entries where data exists, saving space.
-- For training queries, we only care about games WITH goalie data anyway.
-- This is more efficient than indexing NULLs we'll never query.

-- ============================================================
-- Verification Query
-- ============================================================

-- After migration, run this to check coverage:
--
-- SELECT
--     COUNT(*) as total_games,
--     COUNT(home_goalie_gaa) as has_gaa,
--     ROUND(100.0 * COUNT(home_goalie_gaa) / COUNT(*), 1) as coverage_pct
-- FROM game_features
-- WHERE game_date >= '2023-10-01';
--
-- Expected: 0% initially (data will be populated by Session 4 ETL script)
