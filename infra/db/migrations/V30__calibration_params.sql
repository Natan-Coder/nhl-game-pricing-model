-- V30: Store Platt Scaling calibration parameters

CREATE TABLE calibration_params (
    param_id SERIAL PRIMARY KEY,
    param_name TEXT NOT NULL,   -- e.g., 'platt_scaling_moneyline'
    param_a NUMERIC(10, 6),     -- Platt scaling 'a' parameter
    param_b NUMERIC(10, 6),     -- Platt scaling 'b' parameter
    trained_on_n_bets INTEGER,  -- How many bets used for training
    calibration_error_before NUMERIC(5, 4),  -- Before calibration
    calibration_error_after NUMERIC(5, 4),   -- After calibration
    is_active BOOLEAN DEFAULT FALSE,  -- Whether to use in production
    trained_at TIMESTAMP DEFAULT NOW(),
    activated_at TIMESTAMP,
    notes TEXT
);

-- Index for quick lookup
CREATE INDEX idx_calibration_active ON calibration_params(param_name, is_active);

-- Ensure only one active calibration per param_name
CREATE UNIQUE INDEX idx_calibration_unique_active
    ON calibration_params(param_name)
    WHERE is_active = TRUE;

