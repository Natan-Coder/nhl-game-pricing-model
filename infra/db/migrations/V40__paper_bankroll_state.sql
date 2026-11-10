-- V34: Enables tracking simulated paper money bankroll for paper money bets

CREATE TABLE IF NOT EXISTS paper_bankroll_state (
    date DATE PRIMARY KEY,
    starting_bankroll NUMERIC(10,2) NOT NULL,
    ending_bankroll NUMERIC(10,2),
    total_staked NUMERIC(10,2) DEFAULT 0,
    total_profit_loss NUMERIC(10,2) DEFAULT 0,
    num_bets INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);


-- ============================================================
-- Table Comment (Documentation)
-- ============================================================

COMMENT ON TABLE paper_bankroll_state IS
'Tracks simulated "paper money" bankroll state over time.
Mirrors bankroll_state table structure but for paper bets only (is_paper_money = TRUE).
Updated by record_results.py when paper bets settle.
Allows testing aggressive strategies without risking real money.';

-- Column-level comments for clarity
COMMENT ON COLUMN paper_bankroll_state.date IS
'Date of this bankroll snapshot (one row per day)';

COMMENT ON COLUMN paper_bankroll_state.starting_bankroll IS
'Paper bankroll at start of day (equals previous day ending_bankroll)';

COMMENT ON COLUMN paper_bankroll_state.ending_bankroll IS
'Paper bankroll at end of day after all settled bets (starting + profit_loss)';

COMMENT ON COLUMN paper_bankroll_state.total_staked IS
'Total amount staked across all paper bets on this date';

COMMENT ON COLUMN paper_bankroll_state.total_profit_loss IS
'Net profit/loss from all settled paper bets on this date';

COMMENT ON COLUMN paper_bankroll_state.num_bets IS
'Count of settled paper bets on this date';

-- ============================================================
-- Performance Index
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_paper_bankroll_date
ON paper_bankroll_state(date DESC);

-- EXPLANATION:
-- This index optimizes common queries:
--
-- Query 1: "Get most recent paper bankroll"
--   SELECT ending_bankroll FROM paper_bankroll_state
--   ORDER BY date DESC LIMIT 1
--   → Index scan on (date DESC) - very fast
--
-- Query 2: "Get today's paper bankroll"
--   SELECT * FROM paper_bankroll_state WHERE date = CURRENT_DATE
--   → Uses primary key, but DESC index helps with range queries
--
-- Query 3: "Paper bankroll history for last 30 days"
--   SELECT * FROM paper_bankroll_state
--   WHERE date >= CURRENT_DATE - INTERVAL '30 days'
--   ORDER BY date DESC
--   → Uses index for both filtering and sorting
--
-- WHY DESC?
-- Most queries need recent dates first (ORDER BY date DESC).
-- PostgreSQL can scan this index backward efficiently.
-- The primary key already provides ASC ordering, so DESC index adds value.

-- ============================================================
-- Initial Seed Data
-- ============================================================

INSERT INTO paper_bankroll_state (date, starting_bankroll, ending_bankroll, total_staked, total_profit_loss, num_bets)
VALUES (CURRENT_DATE, 1000.00, 1000.00, 0, 0, 0)
ON CONFLICT (date) DO NOTHING;

-- EXPLANATION:
-- Seeds the table with an initial $1000 paper money bankroll for today.
-- ON CONFLICT DO NOTHING: Safe to re-run migration, won't overwrite if row exists
--
-- WHY $1000?
-- - Clean round number for testing
-- - Easy to calculate percentages (5% = $50)
-- - Different from real bankroll ($127.64) makes comparisons obvious
-- - Can be changed later if needed
--
-- ALTERNATIVE: If you want to match your real bankroll instead:
-- INSERT INTO paper_bankroll_state (date, starting_bankroll, ending_bankroll)
-- SELECT CURRENT_DATE, ending_bankroll, ending_bankroll
-- FROM bankroll_state
-- ORDER BY date DESC LIMIT 1
-- ON CONFLICT (date) DO NOTHING;