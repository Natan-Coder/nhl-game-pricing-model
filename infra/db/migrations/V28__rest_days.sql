-- V28: Add rest days tracking for fatigue adjustments
-- Teams on back-to-back games have lower win rates (~42%)

-- Add columns to track rest days
ALTER TABLE game_features
    ADD COLUMN home_rest_days INTEGER,
    ADD COLUMN away_rest_days INTEGER;

-- Add indexes for efficient lookups when calculating rest days
CREATE INDEX idx_game_features_home_team_datetime
    ON game_features(home_team, game_datetime_utc);

CREATE INDEX idx_game_features_away_team_datetime
    ON game_features(away_team, game_datetime_utc);

-- Backfill rest days for existing games
-- For home teams
WITH home_team_games AS (
    SELECT
        game_id,
        home_team,
        game_datetime_utc,
        LAG(game_datetime_utc) OVER (
              PARTITION BY home_team
              ORDER BY game_datetime_utc
          ) as prev_game_time
    FROM game_features
)
UPDATE game_features gf
SET home_rest_days = EXTRACT(DAY FROM (gf.game_datetime_utc - htg.prev_game_time))::INTEGER
FROM home_team_games htg
WHERE gf.game_id = htg.game_id;

-- For away teams
WITH away_team_games AS (
    SELECT
        game_id,
        away_team,
        game_datetime_utc,
        LAG(game_datetime_utc) OVER (
              PARTITION BY away_team
              ORDER BY game_datetime_utc
          ) as prev_game_time
    FROM game_features
)
UPDATE game_features gf
SET away_rest_days = EXTRACT(DAY FROM (gf.game_datetime_utc - atg.prev_game_time))::INTEGER
FROM away_team_games atg
WHERE gf.game_id = atg.game_id;