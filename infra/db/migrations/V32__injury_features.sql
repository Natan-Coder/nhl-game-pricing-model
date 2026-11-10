-- V32: Add injury tracking for line & chemistry adjustments

-- Add columns to track injuries, recent and total
ALTER TABLE game_features
    ADD COLUMN home_recent_injuries INTEGER,
    ADD COLUMN away_recent_injuries INTEGER,
    ADD COLUMN home_total_injuries INTEGER,
    ADD COLUMN away_total_injuries INTEGER;