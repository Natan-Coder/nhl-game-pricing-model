-- V33: Enables tracking of "paper money" bets (simulated bets for testing strategies)                                                                                                                                                │
-- alongside real money bets in the same bet_log table.

ALTER TABLE bet_log
ADD COLUMN IF NOT EXISTS is_paper_money BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN bet_log.is_paper_money IS
'Distinguishes paper money bets (simulated for testing) from real money bets.
FALSE = real money bet, TRUE = paper money bet (simulated).
Paper money bets are settled by record_results.py but update paper_bankroll_state instead of bankroll_state.';

CREATE INDEX IF NOT EXISTS idx_bet_log_paper_money
ON bet_log(is_paper_money, bet_status, bet_placed_at);

DROP INDEX IF EXISTS idx_bet_log_parlay;

CREATE INDEX IF NOT EXISTS idx_bet_log_parlay
ON bet_log(parlay_id, is_paper_money, bet_status)
WHERE is_parlay = true;