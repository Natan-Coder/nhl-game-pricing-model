-- V23: Bet Tracking System
-- Automated bet selection, result tracking, and strategy performance analysis

-- ============================================================
-- Table 1: Betting Strategies
-- ============================================================
CREATE TABLE IF NOT EXISTS betting_strategies (
    strategy_id SERIAL PRIMARY KEY,
    strategy_name TEXT NOT NULL UNIQUE,
    description TEXT,

    -- Selection criteria
    min_edge NUMERIC(5,4) NOT NULL,           -- e.g., 0.05 = 5%
    min_kelly NUMERIC(5,4) NOT NULL,          -- e.g., 0.02 = 2%
    max_kelly NUMERIC(5,4) NOT NULL,          -- e.g., 0.10 = 10%
    min_stake NUMERIC(8,2),                   -- e.g., 5.00
    max_stake NUMERIC(8,2),                   -- e.g., 100.00

    -- Market preferences
    markets TEXT[],                           -- ['moneyline', 'spread', 'total'] or NULL for all
    books TEXT[],                             -- ['FanDuel', 'DraftKings'] or NULL for all

    -- Odds filter (for underdog/favorite strategies)
    odds_filter TEXT,                         -- 'positive' or 'negative' or NULL

    -- Risk management
    kelly_multiplier NUMERIC(3,2) NOT NULL,   -- 1.0 = full Kelly, 0.5 = half Kelly
    max_bets_per_day INT NOT NULL,

    -- Parlay-specific settings
    is_parlay_strategy BOOLEAN DEFAULT false,
    min_parlay_leg_prob NUMERIC(5,4),        -- Only for parlay strategies
    min_parlay_edge NUMERIC(5,4),            -- Only for parlay strategies
    max_parlay_legs INT,                      -- Only for parlay strategies

    -- Status
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- Table 2: Bankroll State
-- ============================================================
CREATE TABLE IF NOT EXISTS bankroll_state (
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
-- Table 3: Bet Log
-- ============================================================
CREATE TABLE IF NOT EXISTS bet_log (
    bet_id SERIAL PRIMARY KEY,
    strategy_id INT REFERENCES betting_strategies(strategy_id),

    -- Bet details
    game_id BIGINT NOT NULL,
    book TEXT NOT NULL,
    market TEXT NOT NULL,
    outcome TEXT NOT NULL,
    line_number INT,                          -- NULL for moneylines

    -- Odds & stake
    american_odds INT NOT NULL,
    decimal_odds NUMERIC(8,4) NOT NULL,
    stake NUMERIC(8,2) NOT NULL,

    -- Model info at time of bet
    model_prob NUMERIC(5,4) NOT NULL,
    implied_prob NUMERIC(5,4) NOT NULL,
    edge NUMERIC(5,4) NOT NULL,
    kelly_fraction NUMERIC(5,4) NOT NULL,

    -- Result tracking
    bet_status TEXT CHECK (bet_status IN ('pending', 'won', 'lost', 'push', 'cancelled')) DEFAULT 'pending',
    profit_loss NUMERIC(8,2),
    result_recorded_at TIMESTAMPTZ,

    -- Parlay tracking
    is_parlay BOOLEAN DEFAULT false,
    parlay_id INT,                           -- Links parlay legs together

    -- Timestamps
    bet_placed_at TIMESTAMPTZ DEFAULT now(),
    game_start_time TIMESTAMPTZ
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_bet_log_strategy ON bet_log(strategy_id);
CREATE INDEX IF NOT EXISTS idx_bet_log_game ON bet_log(game_id);
CREATE INDEX IF NOT EXISTS idx_bet_log_status ON bet_log(bet_status);
CREATE INDEX IF NOT EXISTS idx_bet_log_placed_at ON bet_log(bet_placed_at);
CREATE INDEX IF NOT EXISTS idx_bet_log_parlay ON bet_log(parlay_id) WHERE is_parlay = true;

-- ============================================================
-- Table 4: Parlay Legs
-- ============================================================
CREATE TABLE IF NOT EXISTS parlay_legs (
    parlay_id INT NOT NULL,
    bet_id INT NOT NULL REFERENCES bet_log(bet_id),
    leg_number INT NOT NULL,
    PRIMARY KEY (parlay_id, leg_number)
);

CREATE INDEX IF NOT EXISTS idx_parlay_legs_bet ON parlay_legs(bet_id);

-- ============================================================
-- Materialized View: Strategy Performance
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS strategy_performance AS
SELECT
    s.strategy_id,
    s.strategy_name,
    s.is_parlay_strategy,
    COUNT(b.bet_id) as total_bets,
    COUNT(b.bet_id) FILTER (WHERE b.bet_status = 'won') as wins,
    COUNT(b.bet_id) FILTER (WHERE b.bet_status = 'lost') as losses,
    COUNT(b.bet_id) FILTER (WHERE b.bet_status = 'push') as pushes,
    COUNT(b.bet_id) FILTER (WHERE b.bet_status = 'pending') as pending,
    ROUND(
        COUNT(b.bet_id) FILTER (WHERE b.bet_status = 'won')::NUMERIC /
        NULLIF(COUNT(b.bet_id) FILTER (WHERE b.bet_status IN ('won', 'lost')), 0),
        4
    ) as win_rate,
    SUM(b.stake) as total_staked,
    SUM(b.profit_loss) FILTER (WHERE b.bet_status IN ('won', 'lost', 'push')) as total_profit,
    ROUND(
        SUM(b.profit_loss) FILTER (WHERE b.bet_status IN ('won', 'lost', 'push')) /
        NULLIF(SUM(b.stake), 0),
        4
    ) as roi,
    ROUND(AVG(b.edge), 4) as avg_edge,
    ROUND(AVG(b.kelly_fraction), 4) as avg_kelly,
    ROUND(AVG(b.stake), 2) as avg_stake
FROM betting_strategies s
LEFT JOIN bet_log b ON s.strategy_id = b.strategy_id
WHERE s.is_active = true
GROUP BY s.strategy_id, s.strategy_name, s.is_parlay_strategy;

-- ============================================================
-- Seed Initial Bankroll
-- ============================================================
INSERT INTO bankroll_state (date, starting_bankroll, ending_bankroll)
VALUES (CURRENT_DATE, 1000.00, 1000.00)
ON CONFLICT (date) DO NOTHING;

-- ============================================================
-- Seed Betting Strategies
-- ============================================================

-- Strategy 1: Conservative Value
INSERT INTO betting_strategies (
    strategy_name, description,
    min_edge, min_kelly, max_kelly, min_stake, max_stake,
    markets, books, odds_filter,
    kelly_multiplier, max_bets_per_day, is_parlay_strategy
) VALUES (
    'Conservative Value',
    'Conservative value bets with 5%+ edge, half Kelly sizing',
    0.05, 0.02, 0.05, 5.00, 100.00,
    NULL, NULL, NULL,
    0.50, 3, false
) ON CONFLICT (strategy_name) DO NOTHING;

-- Strategy 2: Aggressive High Edge
INSERT INTO betting_strategies (
    strategy_name, description,
    min_edge, min_kelly, max_kelly, min_stake, max_stake,
    markets, books, odds_filter,
    kelly_multiplier, max_bets_per_day, is_parlay_strategy
) VALUES (
    'Aggressive High Edge',
    'High volume strategy on 3%+ edges, full Kelly sizing',
    0.03, 0.015, 0.10, 5.00, 150.00,
    NULL, NULL, NULL,
    1.00, 10, false
) ON CONFLICT (strategy_name) DO NOTHING;

-- Strategy 3: Moneyline Specialist
INSERT INTO betting_strategies (
    strategy_name, description,
    min_edge, min_kelly, max_kelly, min_stake, max_stake,
    markets, books, odds_filter,
    kelly_multiplier, max_bets_per_day, is_parlay_strategy
) VALUES (
    'Moneyline Specialist',
    'Focus exclusively on moneyline markets with 4%+ edge',
    0.04, 0.02, 0.08, 5.00, 120.00,
    ARRAY['moneyline'], NULL, NULL,
    0.75, 5, false
) ON CONFLICT (strategy_name) DO NOTHING;

-- Strategy 4: Totals Expert
INSERT INTO betting_strategies (
    strategy_name, description,
    min_edge, min_kelly, max_kelly, min_stake, max_stake,
    markets, books, odds_filter,
    kelly_multiplier, max_bets_per_day, is_parlay_strategy
) VALUES (
    'Totals Expert',
    'Specialize in over/under totals markets',
    0.035, 0.015, 0.07, 5.00, 110.00,
    ARRAY['total'], NULL, NULL,
    0.75, 5, false
) ON CONFLICT (strategy_name) DO NOTHING;

-- Strategy 5: Underdog Hunter
INSERT INTO betting_strategies (
    strategy_name, description,
    min_edge, min_kelly, max_kelly, min_stake, max_stake,
    markets, books, odds_filter,
    kelly_multiplier, max_bets_per_day, is_parlay_strategy
) VALUES (
    'Underdog Hunter',
    'Plus-money underdogs with strong value (6%+ edge)',
    0.06, 0.02, 0.06, 5.00, 100.00,
    ARRAY['moneyline'], NULL, 'positive',
    0.50, 4, false
) ON CONFLICT (strategy_name) DO NOTHING;

-- Strategy 6: Favorite Grinder
INSERT INTO betting_strategies (
    strategy_name, description,
    min_edge, min_kelly, max_kelly, min_stake, max_stake,
    markets, books, odds_filter,
    kelly_multiplier, max_bets_per_day, is_parlay_strategy
) VALUES (
    'Favorite Grinder',
    'Volume-based strategy on favorites with steady edges',
    0.03, 0.015, 0.08, 5.00, 130.00,
    ARRAY['moneyline', 'spread'], NULL, 'negative',
    0.75, 8, false
) ON CONFLICT (strategy_name) DO NOTHING;

-- Strategy 7: Line Shopping Master
INSERT INTO betting_strategies (
    strategy_name, description,
    min_edge, min_kelly, max_kelly, min_stake, max_stake,
    markets, books, odds_filter,
    kelly_multiplier, max_bets_per_day, is_parlay_strategy
) VALUES (
    'Line Shopping Master',
    'Only bet when we have the best available line',
    0.04, 0.02, 0.07, 5.00, 115.00,
    NULL, NULL, NULL,
    0.75, 6, false
) ON CONFLICT (strategy_name) DO NOTHING;

-- Strategy 8: Smart Parlay Builder
INSERT INTO betting_strategies (
    strategy_name, description,
    min_edge, min_kelly, max_kelly, min_stake, max_stake,
    markets, books, odds_filter,
    kelly_multiplier, max_bets_per_day, is_parlay_strategy,
    min_parlay_leg_prob, min_parlay_edge, max_parlay_legs
) VALUES (
    'Smart Parlay Builder',
    'Conservative 2-3 leg parlays on high probability bets',
    0.05, 0.02, 0.08, 10.00, 25.00,
    NULL, NULL, NULL,
    0.25, 2, true,
    0.55, 0.03, 3
) ON CONFLICT (strategy_name) DO NOTHING;
