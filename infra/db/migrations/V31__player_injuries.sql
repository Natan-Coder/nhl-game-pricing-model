-- V31: Add player injuries tracking table

CREATE TABLE player_injuries (
    injury_id SERIAL PRIMARY KEY,
    player_name VARCHAR(100) NOT NULL,
    team_abbr VARCHAR(3) NOT NULL,
    date_injured DATE NOT NULL,
    injury_type VARCHAR(50),
    injury_note TEXT,
    is_current BOOLEAN DEFAULT TRUE,
    first_seen_at TIMESTAMP DEFAULT NOW(),
    last_seen_at TIMESTAMP DEFAULT NOW(),
    returned_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_injuries_team_current ON player_injuries(team_abbr, is_current);
CREATE UNIQUE INDEX idx_injuries_unique_active
    ON player_injuries(player_name, is_current)
    WHERE is_current = TRUE;

COMMENT ON COLUMN player_injuries.is_current IS 'TRUE if player still on injury report, FALSE if returned to play';
COMMENT ON COLUMN player_injuries.first_seen_at IS 'Timestamp when injury first appeared on Hockey-Reference';
COMMENT ON COLUMN player_injuries.last_seen_at IS 'Most recent timestamp player was still on injury report';
COMMENT ON COLUMN player_injuries.returned_at IS 'Timestamp when player disappeared from report (returned to play)';