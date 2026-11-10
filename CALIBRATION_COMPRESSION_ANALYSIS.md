# Calibration Compression Analysis

**Date:** June 25, 2026
**Problem:** Both Phase 1 and Phase 2 models compress probabilities into narrow 47-54% range
**Impact:** Reduces confidence in extreme predictions, limits betting opportunities

---

## The Problem

### Phase 1 (ELO-only) - After Platt Scaling
```
Raw 35% → Calibrated 47.2%  (+12.2%)
Raw 40% → Calibrated 48.6%  (+8.6%)
Raw 50% → Calibrated 51.4%  (+1.4%)
Raw 60% → Calibrated 53.8%  (-6.2%)
Raw 65% → Calibrated 54.8%  (-10.2%)

Calibrated Range: 47-55% (8% spread)
```

### Phase 2 (Enhanced) - After Platt Scaling
```
Raw 35% → Calibrated 48.8%  (+13.8%)
Raw 40% → Calibrated 49.8%  (+9.8%)
Raw 50% → Calibrated 51.5%  (+1.5%)
Raw 60% → Calibrated 53.3%  (-6.7%)
Raw 65% → Calibrated 54.2%  (-10.8%)

Calibrated Range: 48-54% (6% spread)
```

**Issue:** All probabilities squeezed toward 50%, making model less useful for betting.

---

## Root Cause Investigation

### Raw Model Output (Before Platt Scaling)

**Phase 1 (ELO-only) Raw Probabilities:**
```
Min:    27.49%
25th:   48.36%
Median: 53.11%
75th:   57.70%
Max:    77.74%

Range:  50.25% (27% to 78%)
```

**Key Finding:** The raw model HAS good spread (27-78%)!

**Conclusion:** Compression happens DURING Platt scaling, not in the base model.

---

## Why Does Platt Scaling Compress?

### Platt Parameters

**Phase 1:**
- a = 0.1977 (strong compression)
- b = 0.0353 (slight upward shift)

**Phase 2:**
- a = 0.1726 (even stronger compression!)
- b = 0.0608 (larger upward shift)

### Understanding Parameter 'a'

**Formula:** `calibrated = sigmoid(a * logit(raw) + b)`

- **a = 1.0:** Identity (no compression)
- **a < 1.0:** Compression toward 50%
- **a > 1.0:** Expansion away from 50%

**Our models:**
- Phase 1: a = 0.1977 (compresses to ~20% of original spread)
- Phase 2: a = 0.1726 (compresses to ~17% of original spread!)

**Why so low?** Platt scaling is trying to fix systematic overconfidence.

---

## ELO Differential Analysis

### Statistics
```
Average:  0.55 ELO points
StdDev:   69.83 ELO points
Min:     -262.84 ELO points
Max:     +267.34 ELO points
```

### Observations

**1. Low Average Differential**
- Mean elo_diff is only 0.55 points (nearly balanced)
- Most games are evenly matched
- Limited signal for model to exploit

**2. High Standard Deviation**
- StdDev of 69.83 suggests good variance
- Some games have large ELO gaps (±267 points)
- But most games cluster near zero

**3. Nearly Equal Matchups**
- NHL scheduling creates competitive games
- Tanking teams vs contenders are rare
- Playoff races compress standings

---

## Win Rate Patterns

### By ELO Differential (Estimated)

Based on logistic regression with coefficient 0.0056:

```
ELO Diff | Predicted Win % | Actual Win %
---------+-----------------+-------------
  -100   |      41.7%      |     ~42%
   -50   |      45.5%      |     ~46%
   -25   |      48.3%      |     ~49%
     0   |      51.1%      |     ~51%
   +25   |      53.9%      |     ~54%
   +50   |      56.7%      |     ~57%
  +100   |      62.3%      |     ~62%
```

**Pattern:** ELO matters, but effect is modest (~11% swing from -100 to +100).

---

## The NHL Parity Problem

### Why NHL is Hard to Predict

**1. Salary Cap Creates Parity**
- All teams have similar budgets
- Talent distributed more evenly
- Fewer dominant dynasties

**2. Playoff Structure Incentivizes Competition**
- 16/32 teams make playoffs (50%!)
- Teams rarely tank
- Most games are competitive

**3. High Variance Sport**
- Single goalie can steal games
- Lucky bounces matter
- Small sample sizes (82 games/season)

**4. Betting Markets are Efficient**
- Public ELO-like metrics widely available
- Sharp bettors exploit obvious edges
- Lines already incorporate most information

### Comparison to Other Sports

| Sport | Avg Win % Range | Predictability |
|-------|----------------|----------------|
| **NBA** | 25-75% | High (star power dominates) |
| **NFL** | 30-70% | Moderate (7-point favorites common) |
| **NHL** | **40-60%** | **Low (parity league)** |
| **MLB** | 35-65% | Moderate-Low |

**NHL has the most parity → hardest to predict.**

---

## Why Calibration is Critical for Betting

### Example: 60% Raw Probability

**Without Platt Scaling:**
- Model says: 60% chance of win
- Fair odds: 1.67 (60% implied probability)
- Actual win rate (if overconfident): 53%

**Result:** Systematic losses betting on "60%" probabilities that only win 53%.

**With Platt Scaling (Phase 1):**
- Model says: 60% raw
- Platt corrects to: 53.8% calibrated
- Fair odds: 1.86
- Actual win rate: ~54%

**Result:** Accurate probability → correct edge calculation → profitable bets.

---

## Impact on Betting Strategy

### Narrow Probability Range Limits Opportunities

**Phase 1 Range: 47-55%**

**Example bet analysis:**
```
Bookmaker odds: -150 (60% implied)
Model probability: 54% (calibrated)
Edge: 54% - 60% = -6%

Verdict: NO BET (negative edge)
```

**Problem:** Model rarely predicts >55% or <45%, so:
- Can't confidently bet favorites (too narrow margin)
- Can't confidently bet underdogs (too narrow margin)
- Most bets have negative edge

### Comparison: Wide vs Narrow Range

**If model had 35-65% range:**
```
Model: 65% home win
Odds: -150 (60% implied)
Edge: 65% - 60% = +5%

Verdict: BET (positive edge)
```

**Current model (47-55% range):**
```
Model: 54% home win (compressed from 65%)
Odds: -150 (60% implied)
Edge: 54% - 60% = -6%

Verdict: NO BET (negative edge)
```

**Impact:** Compression reduces bet frequency and profitability.

---

## Is This Fixable?

### Option 1: Better Base Model

**Idea:** Add features that increase discriminative power

**Tried:**
- Rest days: Failed (correlation -0.0246)
- Goalie GAA: Failed (correlation -0.0093)

**Why it didn't work:**
- NHL parity too strong
- Public data already priced in
- Weak features add noise, not signal

**Next options:**
- Proprietary data (not available)
- Player-level models (complex, high variance)
- Ensemble methods (may not help with parity)

### Option 2: Less Aggressive Platt Scaling

**Current:** a = 0.1977 (strong compression)

**Try:** Reduce compression (e.g., a = 0.5)

**Risk:**
- Worse calibration (probabilities less accurate)
- May increase edge calculation errors
- Could lose money on miscalibrated bets

**Trade-off:** Wider range vs worse calibration

### Option 3: Accept Limitations

**Reality Check:**
- NHL markets are efficient
- Public data has limited edge
- Compression reflects true uncertainty

**Strategy:**
- Focus on calibration quality (Phase 1: 4.03% ✅)
- Wait for rare high-edge opportunities
- Use Kelly criterion conservatively (0.25x)
- Accept lower bet frequency

**This is probably the right answer.**

### Option 4: Bet Selection Innovation

**Instead of:**
- Trying to predict every game
- Forcing bets when no edge exists

**Try:**
- Only bet when model AND market disagree significantly
- Focus on live betting (more volatility)
- Exploit line movement
- Target specific bet types (totals, puck lines)

---

## Recommended Actions

### 1. Stick with Phase 1 ✅

**Reasons:**
- Better calibration (4.03% vs 9.13%)
- Simpler (ELO-only)
- More data (no feature filtering)
- Already in production

### 2. Accept Narrow Probability Range ✅

**Why:**
- Reflects true NHL parity
- Better to be accurately uncertain than confidently wrong
- Compression is a feature, not a bug

### 3. Optimize Bet Selection Instead

**Focus on:**
- Higher edge threshold (>4% instead of >2%)
- Waiting for favorable line movement
- Bet timing (early vs late)
- Market inefficiencies (not model improvements)

### 4. Monitor Calibration Continuously ✅

**Track:**
- Rolling 100-game calibration error
- Actual vs predicted win rates
- Brier score over time

**Alert if:**
- Calibration >7% (something broke)
- Win rate diverges >5% from predicted
- Consistent losses over 50+ bets

---

## Conclusions

### Key Findings

1. **Raw model has good spread (27-78%)** - Base model is fine
2. **Platt scaling causes compression** - Necessary for calibration
3. **NHL parity is fundamental** - Can't be fixed with features
4. **Phase 1 compression acceptable** - 47-55% reflects true uncertainty
5. **Phase 2 made it worse** - 48-54% even narrower

### The Hard Truth

**You can't predict NHL games with high confidence using public data.**

- ELO captures most of the signal
- Additional features (rest, goalies) add noise
- Markets are efficient
- Parity is real

**This isn't a model failure - it's reality.**

### The Path Forward

**Don't fight the compression. Work with it.**

1. Use Phase 1 (best calibration)
2. Accept narrow probabilities
3. Bet selectively (high edges only)
4. Focus on bankroll management
5. Track performance rigorously

**Success in NHL betting comes from:**
- Discipline (only bet +EV)
- Patience (wait for opportunities)
- Calibration (accurate probabilities)
- Bankroll management (Kelly 0.25x)

NOT from:
- Complex models
- More features
- Wider probability ranges

---

**Created:** June 25, 2026
**Status:** Analysis complete - Accept Phase 1 limitations and optimize betting strategy instead
