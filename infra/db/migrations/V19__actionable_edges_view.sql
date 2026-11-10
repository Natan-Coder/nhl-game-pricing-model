-- V19__actionable_edges_view.sql
-- Filter edges to actionable opportunities only
-- Removes outliers, duplicates, and unrealistic odds

CREATE OR REPLACE VIEW actionable_edges AS
WITH filtered_edges AS (
    -- Step 1: Remove obvious outliers
    SELECT
       e.*,
       gf.game_date,
       gf.home_team,
       gf.away_team
    FROM edges e
    JOIN game_features gf ON e.game_id = gf.game_id
    WHERE
        -- Remove unrealistic  implied probabilities
        e.implied_prob BETWEEN 0.05 AND 0.95
        -- Remove extreme edges (likely data errors)
        AND e.edge BETWEEN -0.50 AND 0.15
        -- Only future/today's games
        AND gf.game_date >= CURRENT_DATE
),
ranked_edges AS (
    -- Step 2: Rank edges by best odds for each game/market/outcome
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY game_id, market, outcome
            ORDER BY edge DESC
        ) as rank
    FROM filtered_edges
)
-- Step 3: Take best edge per game/market/outcome, filter to positive edges
SELECT
    game_date,
    game_id,
    home_team,
    away_team,
    market,
    outcome,
    book,
    american_odds,
    implied_prob,
    model_prob,
    edge,
    kelly_fraction,
    suggested_stake,
    computed_at
FROM ranked_edges
WHERE
    rank = 1  -- Best odds only
    AND edge > 0.02  -- Minimum 2% edge
    AND edge < 0.15  -- Maximum 15% edge (sanity check)
ORDER BY edge DESC;

-- Create a more aggressive view for comparison
CREATE OR REPLACE VIEW aggressive_edges AS
SELECT *
FROM actionable_edges
WHERE edge > 0.05 -- 5% edges only
ORDER BY edge DESC;

-- Create a conservative view
CREATE OR REPLACE VIEW conservative_edges AS
SELECT *
FROM actionable_edges
WHERE
    edge > 0.03  -- 3%+ edges
    AND kelly_fraction > 0.01  -- Kelly suggests betting at least 1%
    AND market = 'moneyline'  -- Moneylines only (easier to model)
ORDER BY edge DESC;
