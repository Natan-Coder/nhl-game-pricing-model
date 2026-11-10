-- V29: Add goalie statistics and starting goalie tracking

-- Table 1: Goalie season statistics
-- Stores comprehensive stats for all goalies, updated daily
CREATE TABLE goalie_stats (
    goalie_id INTEGER NOT NULL,
    goalie_name TEXT NOT NULL,
    team_abbr TEXT NOT NULL,
    season INTEGER NOT NULL,  -- e.g., 20252026 for 2025-26 season
    games_played INTEGER DEFAULT 0,
    games_started INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0,
    shots_against INTEGER DEFAULT 0,
    goals_against INTEGER DEFAULT 0,
    save_pct NUMERIC(5,3),  -- e.g., 0.915 = 91.5%
    gaa NUMERIC(4,2),       -- Goals against average, e.g., 2.45
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    ot_losses INTEGER DEFAULT 0,
    shutouts INTEGER DEFAULT 0,
    time_on_ice_seconds INTEGER DEFAULT 0,  -- Total TOI in seconds
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (goalie_id, season),
    CHECK (save_pct >= 0 AND save_pct <= 1),
    CHECK (gaa >= 0),
    CHECK (games_played >= games_started)
);

-- Indexes for fast lookups
CREATE INDEX idx_goalie_stats_team_season ON goalie_stats(team_abbr, season);
CREATE INDEX idx_goalie_stats_name ON goalie_stats(goalie_name);
CREATE INDEX idx_goalie_stats_updated ON goalie_stats(updated_at);

-- Table 2: Starting goalies for each game
-- Populated 2 hours before game time when starters are confirmed
CREATE TABLE game_goalies (
    game_id BIGINT PRIMARY KEY,
    home_goalie_id INTEGER,
    home_goalie_name TEXT,
    away_goalie_id INTEGER,
    away_goalie_name TEXT,
    home_goalie_confirmed BOOLEAN DEFAULT FALSE,
    away_goalie_confirmed BOOLEAN DEFAULT FALSE,
    confirmed_at TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES game_features(game_id) ON DELETE CASCADE
);

CREATE INDEX idx_game_goalies_confirmed ON game_goalies(confirmed_at);

-- Table 3: Add goalie statistics to game features
-- These will be populated when starting goalies are confirmed
ALTER TABLE game_features
    ADD COLUMN home_goalie_id INTEGER,
    ADD COLUMN away_goalie_id INTEGER,
    ADD COLUMN home_goalie_sv_pct NUMERIC(5,3),
    ADD COLUMN away_goalie_sv_pct NUMERIC(5,3),
    ADD COLUMN goalie_advantage INTEGER DEFAULT 0;  -- ELO adjustment (-80 to +80)

-- Comment the columns for documentation
COMMENT ON COLUMN game_features.home_goalie_id IS 'NHL API goalie ID for home starter';
COMMENT ON COLUMN game_features.away_goalie_id IS 'NHL API goalie ID for away starter';
COMMENT ON COLUMN game_features.home_goalie_sv_pct IS 'Home goalie save percentage (season)';
COMMENT ON COLUMN game_features.away_goalie_sv_pct IS 'Away goalie save percentage (season)';
COMMENT ON COLUMN game_features.goalie_advantage IS 'ELO adjustment based on goalie quality difference';

-- Table 4: Goalie rolling statistics (last 10 games)
-- For more recent performance weighting
CREATE TABLE goalie_recent_stats (
    goalie_id        INTEGER NOT NULL,
    as_of_date       DATE    NOT NULL,
    games_last_10    INTEGER DEFAULT 0,
    saves_last_10    INTEGER DEFAULT 0,
    shots_last_10    INTEGER DEFAULT 0,
    save_pct_last_10 NUMERIC(5, 3),
    gaa_last_10      NUMERIC(4, 2),
    PRIMARY KEY (goalie_id, as_of_date)
);

CREATE INDEX idx_goalie_recent_date ON goalie_recent_stats(as_of_date);