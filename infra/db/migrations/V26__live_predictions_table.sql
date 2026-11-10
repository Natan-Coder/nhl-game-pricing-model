-- V26__live_predictions_table.sql

-- Track model predictions before games for live performance monitoring
CREATE TABLE IF NOT EXISTS live_predictions (
    prediction_id SERIAL PRIMARY KEY,
    game_id BIGINT NOT NULL REFERENCES game_features(game_id),
    predicted_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- ELO ratings at prediction time
    home_elo DECIMAL(10,2) NOT NULL,
    away_elo DECIMAL(10,2) NOT NULL,

    -- Predicted probability (home team win)
    predicted_home_win_prob DECIMAL(5,4) NOT NULL,

    -- Actual outcome (filled in after game)
    actual_home_won BOOLEAN,

    -- Derived: was prediction correct?
    prediction_correct BOOLEAN,

    created_at TIMESTAMP DEFAULT NOW(),

    -- Ensure we only have one prediction per game
    UNIQUE(game_id)
);

-- Index for performance queries
CREATE INDEX idx_live_predictions_predicted_at ON live_predictions(predicted_at);
CREATE INDEX idx_live_predictions_game_id ON live_predictions(game_id);

-- Comments for documentation
COMMENT ON TABLE live_predictions IS 'Stores model predictions before games start to track live accuracy';
COMMENT ON COLUMN live_predictions.predicted_home_win_prob IS 'Probability that home team wins (0.0 to 1.0)';
COMMENT ON COLUMN live_predictions.actual_home_won IS 'TRUE if home won, FALSE if away won, NULL if game not finished';