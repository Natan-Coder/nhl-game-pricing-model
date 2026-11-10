# Paper Trading System

**Status:** Deployed - Ready for Testing
**Created:** April 24, 2026
**Database Version:** V39-V40 Applied

---

## Overview

The paper trading system allows you to test betting strategies with simulated money without risking real capital. It runs in parallel with your real betting system, tracking performance separately.

**Key Benefits:**
- Test aggressive strategies safely
- Collect more calibration data faster
- Compare real vs. paper performance side-by-side
- Validate model changes before deploying to real money

---

## System Architecture

### Database Tables

**1. `bet_log` (Modified)**
- Added `is_paper_money` column (BOOLEAN)
- `FALSE` = real money bet
- `TRUE` = paper money bet (simulated)
- Both types tracked in same table for easy comparison

**2. `paper_bankroll_state` (New)**
- Mirrors `bankroll_state` structure
- Tracks paper money bankroll over time
- Initial bankroll: **$1,000.00**
- Updated when paper bets settle

### Pipeline Scripts

**1. `select_paper_bets.py`**
- Mirrors `select_bets.py` logic
- Uses same strategies and edge calculations
- Marks all bets as `is_paper_money = TRUE`
- Can use separate or matching bankroll

**2. Shared Functions (in `select_bets.py`)**
- `get_paper_bankroll()` - Gets current paper bankroll
- `get_paper_exposure()` - Calculates paper exposure
- `should_skip_paper_bet()` - Checks for duplicate paper bets

---

## Current Status

### Paper Bankroll State

```sql
-- Current paper bankroll
SELECT * FROM paper_bankroll_state ORDER BY date DESC LIMIT 1;
```

**As of April 24, 2026:**
- Starting Bankroll: $1,000.00
- Ending Bankroll: $1,000.00
- Total Staked: $0.00
- Profit/Loss: $0.00
- Num Bets: 0

### Paper Bets

```sql
-- Count paper bets
SELECT COUNT(*) FROM bet_log WHERE is_paper_money = TRUE;
```

**Current:** 0 paper bets (system ready but unused)

---

## How to Use

### Daily Workflow

**1. Run Paper Betting Pipeline**

```bash
# Same workflow as real betting, but with paper money

# Step 1: Generate predictions
python -m pipelines.pricing.compute_game_pricing_elos

# Step 2: Calculate edges with calibration
python -m pipelines.pricing.compute_edges

# Step 3: Select paper bets
python -m pipelines.betting.select_paper_bets
```

**2. With Custom Paper Bankroll**

```bash
# Use different bankroll for paper trading
python -m pipelines.betting.select_paper_bets 5000.00
```

This sets a $5,000 paper bankroll instead of matching real money.

**3. Review Paper Bets**

```sql
-- Today's paper bets
SELECT
    bet_id,
    market,
    outcome,
    american_odds,
    stake,
    edge,
    bet_status,
    is_paper_money
FROM bet_log
WHERE is_paper_money = TRUE
  AND DATE(bet_placed_at) = CURRENT_DATE
ORDER BY bet_placed_at DESC;
```

---

## Testing Strategy

### Phase 1: Parallel Testing (Recommended)

Run paper trading alongside real betting to compare:

```bash
# Morning: Select bets for today's games
python -m pipelines.betting.select_bets          # Real money
python -m pipelines.betting.select_paper_bets    # Paper money

# Evening: Record results (handles both automatically)
python -m pipelines.betting.record_results
```

**Compare performance:**
```sql
-- Real vs Paper comparison (last 7 days)
SELECT
    is_paper_money,
    COUNT(*) as num_bets,
    AVG(model_prob) as avg_predicted_prob,
    AVG(CASE WHEN bet_status = 'won' THEN 1.0 ELSE 0.0 END) as win_rate,
    SUM(CASE
        WHEN bet_status = 'won' THEN stake * (decimal_odds - 1)
        WHEN bet_status = 'lost' THEN -stake
        ELSE 0
    END) as profit_loss
FROM bet_log
WHERE created_at >= NOW() - INTERVAL '7 days'
  AND bet_status IN ('won', 'lost')
GROUP BY is_paper_money;
```

### Phase 2: Aggressive Paper Strategies

Test higher-risk strategies with paper money only:

**Examples:**
- Higher Kelly multipliers (0.5x → 1.0x full Kelly)
- Lower edge thresholds (3% → 1%)
- More aggressive bet limits
- Parlay testing

**Modify strategy in database:**
```sql
-- Create aggressive paper-only strategy
INSERT INTO betting_strategies (
    strategy_name,
    description,
    min_edge,
    kelly_multiplier,
    max_bets_per_day,
    is_active
) VALUES (
    'aggressive_paper_test',
    'Paper money test - full Kelly, 1% edge threshold',
    0.01,  -- 1% edge instead of 3%
    1.00,  -- Full Kelly instead of 0.25x
    10,    -- More bets per day
    TRUE
);
```

Then run only paper bets with this strategy enabled.

---

## Monitoring & Analysis

### Daily Checks

**1. Paper Bet Summary**
```sql
SELECT
    DATE(bet_placed_at) as bet_date,
    COUNT(*) as num_bets,
    SUM(stake) as total_staked,
    COUNT(*) FILTER (WHERE bet_status = 'won') as wins,
    COUNT(*) FILTER (WHERE bet_status = 'lost') as losses,
    COUNT(*) FILTER (WHERE bet_status = 'pending') as pending
FROM bet_log
WHERE is_paper_money = TRUE
GROUP BY DATE(bet_placed_at)
ORDER BY bet_date DESC
LIMIT 7;
```

**2. Paper Bankroll History**
```sql
SELECT
    date,
    starting_bankroll,
    ending_bankroll,
    total_profit_loss,
    num_bets,
    CASE
        WHEN starting_bankroll > 0
        THEN (ending_bankroll - starting_bankroll) / starting_bankroll * 100
    END as roi_pct
FROM paper_bankroll_state
ORDER BY date DESC
LIMIT 30;
```

### Weekly Analysis

**Calibration Check (Paper vs Real)**
```sql
SELECT
    is_paper_money,
    COUNT(*) as sample_size,
    ROUND(AVG(model_prob)::numeric, 4) as avg_predicted,
    ROUND(AVG(CASE WHEN bet_status = 'won' THEN 1.0 ELSE 0.0 END)::numeric, 4) as avg_actual,
    ROUND(ABS(AVG(model_prob) - AVG(CASE WHEN bet_status = 'won' THEN 1.0 ELSE 0.0 END))::numeric, 4) as calibration_error
FROM bet_log
WHERE created_at >= NOW() - INTERVAL '7 days'
  AND bet_status IN ('won', 'lost')
GROUP BY is_paper_money;
```

**Expected Results:**
- Calibration error should be similar for both
- If paper diverges significantly, investigate strategy differences

---

## Common Use Cases

### 1. Model Validation Before Deployment

Before activating new Platt scaling parameters:

```bash
# Test new calibration with paper money first
# 1. Create new param set in calibration_params
# 2. Temporarily activate for edge calculation
# 3. Run paper betting for 1-2 weeks
# 4. Compare to real money performance
# 5. If better, activate for real money
```

### 2. Strategy Testing

Test modifications without risk:

```bash
# Scenario: What if we used 0.5x Kelly instead of 0.25x?
# 1. Clone betting strategy with new Kelly multiplier
# 2. Run paper bets with new strategy
# 3. Compare ROI and volatility to real money
# 4. Decide whether to deploy
```

### 3. Feature Validation

When adding new features (rest days, goalies, injuries):

```bash
# 1. Train model with new features
# 2. Generate predictions with new model
# 3. Run paper betting with new predictions
# 4. Compare performance to baseline (real money)
# 5. If improvement is significant, deploy to real money
```

### 4. Collecting Calibration Data

Increase data collection rate:

```bash
# Use paper money to bet on ALL edges (no minimum threshold)
# Real money: Only high-confidence bets (>3% edge)
# Paper money: All bets (>0% edge)
# Result: More calibration data points faster
```

---

## Important Notes

### Paper Money Limitations

**1. Not a Perfect Simulation**
- Paper money doesn't account for bet limits
- No slippage or line movement
- Assumes all bets get filled at listed odds

**2. Psychological Differences**
- Paper trading lacks emotional pressure
- Real money decisions may differ
- Use paper as validation, not replacement

**3. Same Calibration**
- Paper and real money use same model
- Calibration issues affect both equally
- Don't expect dramatically different results

### Best Practices

**DO:**
- Run paper trading in parallel with real money
- Use paper to test risky changes
- Monitor both for calibration drift
- Compare strategies side-by-side

**DON'T:**
- Rely solely on paper trading results
- Skip real money validation
- Ignore differences between paper and real performance
- Use paper trading to delay deployment indefinitely

---

## Database Schema Reference

### bet_log.is_paper_money

```sql
-- Column definition
ALTER TABLE bet_log
ADD COLUMN is_paper_money BOOLEAN NOT NULL DEFAULT FALSE;

-- Index for fast filtering
CREATE INDEX idx_bet_log_paper_money
ON bet_log(is_paper_money, bet_status, bet_placed_at);
```

### paper_bankroll_state

```sql
CREATE TABLE paper_bankroll_state (
    date DATE PRIMARY KEY,
    starting_bankroll NUMERIC(10,2) NOT NULL,
    ending_bankroll NUMERIC(10,2),
    total_staked NUMERIC(10,2) DEFAULT 0,
    total_profit_loss NUMERIC(10,2) DEFAULT 0,
    num_bets INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_paper_bankroll_date
ON paper_bankroll_state(date DESC);
```

---

## Troubleshooting

### Issue: Paper bets not showing up

**Check:**
```sql
-- Are bets marked correctly?
SELECT is_paper_money, COUNT(*)
FROM bet_log
GROUP BY is_paper_money;
```

**Fix:**
- Verify `select_paper_bets.py` is using `log_paper_bet()` function
- Check logs for errors during bet logging

### Issue: Paper bankroll not updating

**Check:**
```sql
-- When was paper bankroll last updated?
SELECT * FROM paper_bankroll_state
ORDER BY date DESC LIMIT 5;
```

**Fix:**
- Run `record_results.py` to settle paper bets
- Verify `record_results.py` handles `is_paper_money = TRUE`

### Issue: Duplicate paper bets

**Check:**
```sql
-- Find duplicates
SELECT game_id, market, outcome, COUNT(*)
FROM bet_log
WHERE is_paper_money = TRUE
GROUP BY game_id, market, outcome
HAVING COUNT(*) > 1;
```

**Fix:**
- `should_skip_paper_bet()` should prevent duplicates
- Verify function is being called in selection logic

---

## Next Steps

### Immediate (April 24, 2026)

- [ ] Run first paper betting test
- [ ] Verify bets are logged correctly
- [ ] Check paper bankroll updates after settlement

### After 1 Week

- [ ] Compare paper vs real performance
- [ ] Analyze calibration differences
- [ ] Document findings

### After 1 Month

- [ ] Decide on strategy changes based on paper results
- [ ] Consider deploying successful paper strategies to real money
- [ ] Update this document with lessons learned

---

## Related Documentation

- **`PROJECT_STATUS.md`** - Overall project status
- **`DEPLOYMENT_CHECKLIST.md`** - Deployment workflow
- **`PHASE_1_RESULTS.md`** - Model performance results
- **`FEATURE_ENGINEERING_TODO.md`** - Future features to test

---

**Created:** April 24, 2026
**Last Updated:** April 24, 2026
**Status:** 🟢 Ready for Testing
**Next Review:** After first week of paper trading
