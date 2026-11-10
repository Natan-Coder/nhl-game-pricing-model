# NHL Betting Model - Success Metrics & Validation Criteria

**Date:** March 22, 2026
**Purpose:** Define clear, measurable criteria that the new model MUST meet before betting real money

---

## Critical Success Criteria

**ALL of these must be met before going live. NO EXCEPTIONS.**

### 1. Model Performance Metrics

#### PRIMARY: Calibration (Most Important)
- **Calibration Error < 3%** on test set (2nd half of 2025 season)
  - Measure: Mean absolute difference between predicted probabilities and actual outcomes
  - Why critical: The 2025-26 model failed because probabilities were wrong, not just miscalibrated
  - Test: Plot calibration curve (predicted vs actual) - should be close to diagonal line

#### SECONDARY: Predictive Accuracy
- **Accuracy > 53%** on test set
  - Baseline (picking favorites): ~55%
  - Baseline (logistic regression on ELO only): Need to measure
  - Target: Beat baseline by at least 1%

#### TERTIARY: Probability Quality
- **Brier Score < 0.240** on test set
  - Measures quality of probabilistic predictions
  - Lower is better (0 = perfect, 0.25 = random coin flip)

---

### 2. Backtest Performance Metrics

#### ROI (Return on Investment)
- **Backtest ROI > 5%** on 2023-2024 seasons
  - Calculated using Kelly criterion with 0.25x multiplier
  - Min edge threshold: 2-4% (to be optimized)
  - Why 5%?: Need margin above break-even to account for real-world friction

#### Risk-Adjusted Returns
- **Sharpe Ratio > 1.5**
  - Measures return per unit of risk
  - Formula: (Average ROI - 0) / Std Dev of ROI
  - >1.5 considered "good" in quantitative trading

#### Drawdown Protection
- **Max Drawdown < 20%**
  - Largest peak-to-trough decline in bankroll
  - Ensures we don't lose too much in bad streaks
  - 20% threshold allows recovery without destroying confidence

---

### 3. Volume & Coverage

#### Bet Volume
- **Minimum 200 bets** in backtest per season
  - Ensures statistical significance
  - Too few bets = can't trust ROI estimate
  - 200 bets ≈ ~25% of games (acceptable coverage)

#### Edge Distribution
- **At least 50 bets with edge > 5%**
  - Ensures we have "high confidence" opportunities
  - High-edge bets should drive majority of profit

---

### 4. Feature Validation

#### Feature Impact
- **Each feature must improve test accuracy by > 0.1%**
  - Measure by removing feature and re-testing
  - Prevents overfitting to noise
  - Keep feature set minimal and interpretable

#### Feature Importance
- **Top 5 features must make logical sense**
  - Use SHAP values to understand feature importance
  - If "days since last full moon" is top feature → problem!
  - Ensures model is learning real patterns, not spurious correlations

#### No Data Leakage
- **ALL features must be available before game start**
  - Check: Can we compute this feature at bet placement time?
  - Common leakage: Using final game stats, post-game data

---

### 5. Production Validation

#### Paper Trading
- **50 games** of paper trading with positive results
  - Track picks without betting real money
  - Calibration should match backtest (within 2%)
  - ROI should be positive (allows for small sample variance)

#### Small Stakes Testing
- **50 games** at 0.1x Kelly (1/10th normal bet size)
  - Max $10/bet or 1% of bankroll (whichever smaller)
  - Calibration still good?
  - ROI still positive?

#### Pipeline Reliability
- **7 consecutive days** with no data pipeline failures
  - All data sources ingesting correctly
  - Features computed without errors
  - Model predictions generated on schedule

---

## Red Flags - Immediate Stop Criteria

**If ANY of these occur, STOP betting immediately and investigate:**

### During Development
- [ ] Calibration error > 5% on validation set
- [ ] Backtest ROI < 0% (losing money even in backtest)
- [ ] Feature importance shows illogical patterns
- [ ] Train/test performance gap > 2% (overfitting)

### During Paper Trading
- [ ] Calibration drift > 3% from backtest
- [ ] ROI < -10% after 30 games
- [ ] Data pipeline fails to update for 2+ consecutive days

### During Live Betting
- [ ] Real ROI diverges from backtest ROI by > 5%
- [ ] Calibration error increases > 5%
- [ ] Bankroll drawdown > 15% in one week
- [ ] Any bet placed due to data error or bug

---

## Measurement Methodology

### Calibration Error
```python
# Group predictions into bins (e.g., 50-55%, 55-60%, etc.)
# For each bin, compare average predicted prob to actual win rate
bins = [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8]
calibration_error = mean(abs(predicted_prob - actual_win_rate) for each bin)
```

### Brier Score
```python
# For each game prediction
brier_score = mean((predicted_prob - actual_outcome)^2)
# actual_outcome is 0 or 1 (loss or win)
```

### Sharpe Ratio
```python
# Calculate ROI for each bet
roi_per_bet = (profit - loss) / stake
sharpe = mean(roi_per_bet) / std(roi_per_bet) * sqrt(num_bets)
```

### Max Drawdown
```python
# Track cumulative profit over time
cumulative_profit = [bet1_profit, bet1+bet2_profit, ...]
peak = cumulative_max(cumulative_profit)
drawdown = (cumulative_profit - peak) / bankroll
max_drawdown = min(drawdown)  # Most negative value
```

---

## Progressive Validation Gates

**You must pass EACH gate before moving to the next:**

### Gate 1: Development
- [ ] Model passes all "Model Performance Metrics"
- [ ] Model passes all "Feature Validation" criteria
- [ ] Backtest shows positive ROI

**Pass Gate 1 → Proceed to Backtest Validation**

### Gate 2: Backtest Validation
- [ ] Backtest ROI > 5% on 2023-2024 seasons
- [ ] Sharpe ratio > 1.5
- [ ] Max drawdown < 20%
- [ ] Volume > 200 bets per season

**Pass Gate 2 → Proceed to Paper Trading**

### Gate 3: Paper Trading
- [ ] 50 games tracked (no real money)
- [ ] Calibration matches backtest (within 2%)
- [ ] ROI is positive (can be small sample variance)
- [ ] No data pipeline failures

**Pass Gate 3 → Proceed to Small Stakes**

### Gate 4: Small Stakes Testing
- [ ] 50 games at 0.1x Kelly
- [ ] ROI still positive
- [ ] Calibration still good
- [ ] No red flags triggered

**Pass Gate 4 → Scale to Full Betting (0.25x Kelly)**

### Gate 5: Full Scale (Ongoing)
- [ ] 200 games at 0.25x Kelly
- [ ] ROI matches backtest expectations (within 3%)
- [ ] Calibration stable
- [ ] Consider scaling to 0.5x Kelly if very confident

---

## Success Dashboard

**Track these metrics weekly:**

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Calibration Error | < 3% | TBD | ⏳ |
| Test Accuracy | > 53% | TBD | ⏳ |
| Brier Score | < 0.240 | TBD | ⏳ |
| Backtest ROI | > 5% | TBD | ⏳ |
| Sharpe Ratio | > 1.5 | TBD | ⏳ |
| Max Drawdown | < 20% | TBD | ⏳ |
| Paper Trading ROI | > 0% | TBD | ⏳ |
| Live ROI | Match backtest ± 3% | TBD | ⏳ |

**Legend:** ⏳ Not Started | 🚧 In Progress | ✅ Passed | ❌ Failed

---

## Comparison to 2025-26 Model (What Went Wrong)

| Metric | 2025-26 Model | Target for New Model |
|--------|---------------|---------------------|
| Calibration Error | ~8-10% (estimated) | < 3% |
| Test Accuracy | Unknown (not measured) | > 53% |
| Backtest ROI | Not done properly | > 5% |
| Paper Trading | SKIPPED | 50 games required |
| Small Stakes | SKIPPED | 50 games required |
| Real ROI | -14.88% | > 5% |

**Key Lesson:** We went live without proper validation. This time, NO SHORTCUTS.

---

## When to Abandon/Rebuild Again

**If after 3 months of development, you cannot achieve:**
- Calibration error < 3% on test set
- Backtest ROI > 0%

**Then consider:**
- Gathering more/better data (injuries, etc.)
- Trying different modeling approaches (neural nets, ensembles)
- Accepting that NHL markets might be too efficient to beat

**DO NOT lower standards just to go live.** Better to accept defeat than lose more money.

---

## Final Checklist Before First Real Bet

Print this out and check EVERY box:

- [ ] I have 3+ seasons of training data
- [ ] I have held-out test data (never used in training)
- [ ] Model calibration error < 3% on test set
- [ ] Backtest ROI > 5% on 2023-2024 seasons
- [ ] Sharpe ratio > 1.5
- [ ] Max drawdown < 20%
- [ ] All features make logical sense
- [ ] No data leakage detected
- [ ] Paper traded 50 games successfully
- [ ] Small stakes tested 50 games successfully
- [ ] Data pipeline has run 7+ days without failure
- [ ] I have a plan for what to do if model starts failing
- [ ] I am using Kelly criterion with 0.25x multiplier (or lower)
- [ ] I have defined stop-loss rules and will follow them
- [ ] I have read this entire document and understand every metric

**If ANY box is unchecked, DO NOT BET REAL MONEY.**

---

**Remember:** The goal is not to start betting as soon as possible. The goal is to build a PROFITABLE, SUSTAINABLE system that makes money over the long term. Patience and discipline are essential.

**Last Updated:** March 22, 2026
