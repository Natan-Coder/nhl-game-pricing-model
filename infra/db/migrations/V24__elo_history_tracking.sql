-- V25: ELO History Tracking
-- Store historical ELO ratings over time for backtesting and model validation

-- ============================================================
-- Table: team_elo_history
-- ============================================================
-- Purpose: Track team ELO ratings at different points in time
--
-- Use Case: When evaluating model accuracy, we need to know:
--   "What was Team X's ELO on Date Y?"
-- This allows us to replay predictions using historical ratings
-- rather than current ratings.
CREATE TABLE IF NOT EXISTS team_elo_history (
    history_id SERIAL PRIMARY KEY,

    -- Team identifier (matches team_abbr in your system)
    team_code TEXT NOT NULL,

    -- The date this ELO rating is valid for
    -- Typically the date AFTER a game (post-update)
    game_date DATE NOT NULL,

    -- The ELO rating value at this point in time
    elo_rating NUMERIC(8,2) NOT NULL,

    -- How many games this team has played up to this date
    -- Useful for filtering early-season unreliable ratings
    games_played INT DEFAULT 0,

    -- Season identifier (e.g., '2023-24')
    -- Makes it easy to query specific seasons
    season TEXT,

    -- Audit trail
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Ensure one ELO per team per date per season
    -- If we re-run replay, this prevents duplicates
    UNIQUE(team_code, game_date, season)
);

-- ============================================================
-- Indexes for Performance
-- ============================================================

-- Primary lookup pattern: "What was Team X's ELO on Date Y?"
CREATE INDEX IF NOT EXISTS idx_elo_history_team_date
ON team_elo_history(team_code, game_date);

-- Filter by season
CREATE INDEX IF NOT EXISTS idx_elo_history_season
ON team_elo_history(season);

-- Sort by date (for chronological queries)
CREATE INDEX IF NOT EXISTS idx_elo_history_date
ON team_elo_history(game_date);

-- ============================================================
-- Comments for Documentation
-- ============================================================

COMMENT ON TABLE team_elo_history IS
'Historical ELO ratings for teams over time. Used for backtesting and model validation.';

COMMENT ON COLUMN team_elo_history.team_code IS
'Team abbreviation (e.g., BOS, TOR, TBL)';

COMMENT ON COLUMN team_elo_history.game_date IS
'Date this ELO rating is valid for (typically after games on this date have been processed)';

COMMENT ON COLUMN team_elo_history.elo_rating IS
'ELO rating value (typically 1200-1800 range, with 1500 as average)';

COMMENT ON COLUMN team_elo_history.games_played IS
'Total games played up to this date (useful for filtering unreliable early-season ratings)';

COMMENT ON COLUMN team_elo_history.season IS
'Season identifier for easy filtering (e.g., "2023-24", "2024-25")';