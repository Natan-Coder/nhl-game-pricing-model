-- V25__elo_history_per_game.sql

-- Add game_id column to track which game these ELOs were before
ALTER TABLE team_elo_history
    ADD COLUMN IF NOT EXISTS game_id BIGINT;

-- Drop old constraint (one snapshot per day)
ALTER TABLE team_elo_history
    DROP CONSTRAINT IF EXISTS team_elo_history_team_code_game_date_season_key;

-- Drop new constraint if it exists (for idempotency)
ALTER TABLE team_elo_history
    DROP CONSTRAINT IF EXISTS team_elo_history_team_code_game_id_key;

-- Add new constraint (one snapshot per game)
ALTER TABLE team_elo_history
    ADD CONSTRAINT team_elo_history_team_code_game_id_key
        UNIQUE (team_code, game_id);

-- Add index for efficient lookups
CREATE INDEX IF NOT EXISTS idx_team_elo_history_game_id
    ON team_elo_history(game_id);
