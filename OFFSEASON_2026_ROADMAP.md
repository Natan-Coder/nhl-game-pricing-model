# Offseason 2026 Roadmap - Phase 2 Model Enhancement

**Created:** June 1, 2026
**Last Updated:** June 25, 2026
**Season Target:** 2026-27 NHL Season (starts October 2026)
**Timeline:** COMPLETED (June 7-25, 2026)
**Effort:** ~2 hours actual (vs 12-15 hour estimate)

**FINAL STATUS:** All sessions complete. Phase 2 NOT recommended for deployment.

---

## 📈 Progress Tracker

| Session | Status | Date Completed | Time Spent | Notes |
|---------|--------|----------------|------------|-------|
| **Session 1: Rest Days** | ✅ COMPLETE | June 7, 2026 | ~45 min | 4,253 games updated, 99.4% coverage |
| **Session 2: Verify Rest Days** | ✅ COMPLETE | June 7, 2026 | ~20 min | Validation passed, 99.3% coverage confirmed |
| **Session 3: Goalie GAA Setup** | ✅ COMPLETE | June 24, 2026 | ~20 min | V41 migration applied, NULL strategy chosen |
| **Session 4: Goalie GAA Data** | ✅ COMPLETE | June 24, 2026 | ~30 min | 4,060 games updated, 95.4% coverage |
| **Session 5: Train Enhanced Model** | ✅ COMPLETE | June 24, 2026 | ~45 min | 55.19% accuracy, features underperformed |
| **Session 6: Retrain Calibration** | ✅ COMPLETE | June 24, 2026 | ~30 min | 9.13% calibration (worse than Phase 1) |

**Total Progress:** 6/6 sessions complete (100%)

**Investigation Phase:** June 25, 2026 - Root cause analysis completed

---

## ⚠️ FINAL DECISION: DO NOT DEPLOY PHASE 2

**After completing all 6 sessions and conducting comprehensive investigation:**

### Performance Results

| Metric | Phase 1 (ELO only) | Phase 2 (Enhanced) | Change | Target Met? |
|--------|-------------------|-------------------|---------|-------------|
| **Accuracy** | 54.98% | 55.19% | +0.21% | ❌ (needed +0.5%) |
| **Calibration** | **4.03%** | **9.13%** | **+5.10%** | ❌ **WORSE** |
| **Brier Score** | 0.2473 | 0.2467 | -0.0006 | ❌ (needed -0.01) |
| **Sample Size** | 712 games | 511 games | -28% | ❌ Lost data |

### Why Phase 2 Failed

**Rest Days Feature:**
- Coefficient: -0.0002 (essentially zero)
- Correlation with wins: -0.0246 (useless)
- NHL scheduling is balanced: 50.9% games have equal rest
- Feature added NO predictive value

**Goalie GAA Feature:**
- Coefficient: -0.0744 (moderate but weak)
- Correlation with wins: -0.0093 (weaker than rest days)
- Season-level aggregation too coarse
- Minimal predictive value

**Calibration Degradation:**
- Phase 2 calibration 127% worse than Phase 1 (9.13% vs 4.03%)
- Weak features added noise instead of signal
- Platt scaling compressed probabilities even more (48-54% range)
- Unacceptable for production betting

### Success Criteria Not Met

**Required at least ONE of:**
- ❌ Accuracy +0.5% (got +0.21%)
- ❌ Brier -0.01 (got -0.0006)
- ❌ Calibration -1% (got +5.10% - WORSE!)

**Result:** Phase 2 FAILED all success criteria.

### Recommendation

**CONTINUE USING PHASE 1 (ELO-only) MODEL FOR 2026-27 SEASON**

**Reasons:**
1. Superior calibration (4.03% vs 9.13%) - CRITICAL for betting
2. More test data (712 vs 511 games)
3. Simpler to maintain (single feature)
4. Already validated and in production
5. Phase 2 added complexity with no benefit

**See full analysis in:**
- `PHASE_2_RECOMMENDATIONS.md` - Final recommendations and path forward
- `PHASE_1_VS_PHASE_2_COMPARISON.md` - Detailed performance comparison
- `CALIBRATION_COMPRESSION_ANALYSIS.md` - Root cause of calibration issues
- `SESSIONS_3_6_COMPLETION.md` - Complete session-by-session summary

**Total Progress:** 6/6 sessions complete (100%) - Investigation complete

---

## 🎯 Mission: Build Phase 2 Model with Enhanced Features

**Current State:** Phase 1 ELO-only model deployed (54.98% accuracy, 4.03% calibration)

**Goal:** Add rest days + goalie features → Phase 2 multi-feature model

**Expected Improvement:**
- Accuracy: 55% → 57-58%
- Calibration: 4% → 2-3%
- Probability discrimination: Reduce compression from 47-54% range

---

## 📊 ROI Analysis: Why This Order?

| Task | Time | Model Impact | Data Availability | ROI Score |
|------|------|--------------|-------------------|-----------|
| **Rest Days** | 2-3 hrs | High | 100% | ⭐⭐⭐⭐⭐ |
| **Goalie GAA** | 4-6 hrs | High | 97% | ⭐⭐⭐⭐ |
| **Model Retrain** | 2 hrs | Very High | Depends | ⭐⭐⭐⭐⭐ |
| **Injuries** | 3-4 hrs | Medium | 27% | ⭐⭐ |
| **Infrastructure** | Ongoing | Low | N/A | ⭐⭐ |

**Key Insight:** Rest days + goalie stats are high-value, available data. Injuries have limited historical coverage (only 2025-26 season forward), so lower priority.

---

## 🛣️ The Path: 6 Weekend Sessions

### **Session 1: Rest Days Feature (2-3 hours)**
**When:** Weekend 1
**Goal:** Calculate and populate rest days for all games

#### What You'll Build
`pipelines/etl/calculate_rest_days.py`

#### Similar Script Reference
`pipelines/etl/update_game_features_elos.py`
- Lines 40-120: Pattern for iterating games chronologically
- Lines 80-95: UPDATE game_features syntax
- Lines 15-30: Database connection and logging setup

#### The Structure
```python
# 1. Import section (copy pattern from update_game_features_elos.py)
#    - psycopg for database
#    - config for DATABASE_URL
#    - logging for output

# 2. Main logic:
#    - Get all games ordered by date
#    - For each team in each game:
#        * Find their previous game (self-join on games table)
#        * Calculate days_between = current_date - previous_date
#        * UPDATE game_features SET home_rest_days = days_between

# 3. Edge case handling:
#    - First game of season: NULL (no previous game)
#    - Season opener after summer: Calculate from previous season finale

# 4. Testing:
#    - Run on one team first (--team "BOS" --limit 10)
#    - Then full backfill
```

#### Key Queries You'll Need
```sql
-- Find previous game for a team
SELECT game_id, game_date
FROM games
WHERE (home_team = 'BOS' OR away_team = 'BOS')
  AND game_date < '2026-01-15'
ORDER BY game_date DESC
LIMIT 1;

-- Calculate rest days (PostgreSQL date math)
SELECT
    current_game.game_date - previous_game.game_date as rest_days
FROM games current_game, games previous_game
WHERE ...;
```

#### Learning Checkpoints
Before coding, answer:
1. Which tables do you need? (Hint: `games` and `game_features`)
2. How do you find "previous game for team X"? (Hint: self-join with ORDER BY)
3. What edge case might break this? (Hint: first game of season)

#### Success Criteria
- Coverage: >95% (some games legitimately have no previous game)
- Distribution: ~40% have 1 day rest, ~30% have 2 days, ~20% have 3+ days
- Back-to-backs: ~5-8% of games (0 days rest)

#### ✅ Session 1 COMPLETED - June 7, 2026

**Actual Results:**
- ✅ Script created: `pipelines/etl/calculate_rest_days.py` (62 lines)
- ✅ Games updated: 4,253 games on Supabase production database
- ✅ Coverage achieved: 99.4% (4,226 games with rest data)
- ✅ Distribution: 54.2% (2 days), 14.4% (1 day), 20.3% (3 days) - Perfect!
- ✅ Time taken: ~45 minutes (faster than estimated!)
- ✅ No errors on first run

**What was learned:**
- Self-join SQL pattern for finding previous records
- Correlated subqueries in UPDATE statements
- PostgreSQL date arithmetic
- Production database ETL workflow

**File created:** `pipelines/etl/calculate_rest_days.py`

---

### **Session 2: Verify Rest Days (1 hour)**
**When:** Weekend 2
**Goal:** Confirm calculation worked correctly

#### Similar Script Reference
`pipelines/analysis/diagnose_rest_days_coverage.py` (already exists!)

#### What to Do
```bash
# 1. Run your calculation script
python -m pipelines.etl.calculate_rest_days

# 2. Check coverage
python -m pipelines.analysis.diagnose_rest_days_coverage

# Expected output:
# Coverage: 94-96%
# NULL values: 4-6% (first games of season/career)
```

#### Validation Queries
```sql
-- Check distribution
SELECT
    home_rest_days,
    COUNT(*) as num_games,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as pct
FROM game_features
WHERE home_rest_days IS NOT NULL
GROUP BY home_rest_days
ORDER BY home_rest_days;

-- Expected distribution:
-- 0 days: ~5-8%  (back-to-backs)
-- 1 day: ~35-45% (most common)
-- 2 days: ~30-40%
-- 3+ days: ~15-25%

-- Spot check specific teams
SELECT
    game_date,
    home_team,
    away_team,
    home_rest_days,
    away_rest_days
FROM game_features
WHERE (home_team = 'BOS' OR away_team = 'BOS')
  AND game_date >= '2025-10-01'
ORDER BY game_date
LIMIT 20;
```

#### Red Flags to Watch For
- ❌ All values are 1 (logic error in calculation)
- ❌ Coverage <80% (query missing many games)
- ❌ Negative values (date math error)
- ❌ Values >30 days (not filtering by season properly)

#### ✅ Session 2 COMPLETED - June 7, 2026

**Actual Results:**
- ✅ Validation passed with flying colors
- ✅ Coverage: 99.3% (4,226/4,254 games)
- ✅ NULL values: 28 games (0.7%) - all are season openers (expected)
- ✅ Distribution: Perfect match to NHL scheduling patterns
- ✅ Spot checks: Boston Bruins October schedule verified correct
- ✅ Edge cases: NULL handling working perfectly
- ✅ Time taken: ~20 minutes (3x faster than estimated!)

**Script improvements:**
- Enhanced logging messages for clarity
- Now explicitly states which columns are updated (`home_rest`, `away_rest`)
- Explains why NULL values exist

**Key discovery:**
- Found duplicate column sets: `home_rest` vs `home_rest_days`
- Your script correctly uses `home_rest` / `away_rest` (99.3% coverage)
- Legacy columns `home_rest_days` / `away_rest_days` have only 9.7% coverage
- **Use `home_rest` / `away_rest` for model training**

**File updated:** `pipelines/etl/calculate_rest_days.py` (better logging)

---

### **Session 3: Goalie Stats - Setup (2 hours)**
**When:** Weekend 3
**Goal:** Add GAA columns to game_features and run migration

#### The Decision: GAA vs Save%

**Option A: Use GAA (Goals Against Average)** ← RECOMMENDED
- ✅ Already calculated in `calculate_goalie_stats.py` (line 96)
- ✅ No new data sources needed
- ✅ GAA correlates well with wins
- ❌ Need to add columns to `game_features` (1 new migration)
- Time: ~2 hours

**Option B: Fetch Save% from NHL API**
- ✅ Better metric (more predictive than GAA)
- ❌ Need to modify `ingest_goalie_stats.py` to fetch shots data
- ❌ NHL API can be unreliable
- ❌ More complex ETL pipeline
- Time: ~4-6 hours

**Recommendation:** Start with GAA. If it improves model significantly, upgrade to save% later.

#### What You'll Build
`infra/db/migrations/V41__add_goalie_gaa_to_features.sql`

#### Similar Migration Reference
`infra/db/migrations/V29__goalie_tables.sql`
- Lines 15-25: ALTER TABLE syntax
- Lines 30-40: Index creation patterns
- Shows how to add columns to existing tables

#### Your Migration
```sql
-- V41__add_goalie_gaa_to_features.sql
-- Add GAA (Goals Against Average) columns to game_features

-- Add columns for goalie GAA
ALTER TABLE game_features
ADD COLUMN home_goalie_gaa DECIMAL(4,2),
ADD COLUMN away_goalie_gaa DECIMAL(4,2);

-- Create index for faster queries
CREATE INDEX idx_game_features_goalie_gaa
ON game_features(home_goalie_gaa, away_goalie_gaa);

-- Add comment for documentation
COMMENT ON COLUMN game_features.home_goalie_gaa IS
    'Home starting goalie GAA as of this game date';
COMMENT ON COLUMN game_features.away_goalie_gaa IS
    'Away starting goalie GAA as of this game date';
```

#### Apply Migration
```bash
# Check current migration status
cd infra/docker
docker-compose exec postgres psql -U postgres -d postgres -c "SELECT version FROM flyway_schema_history ORDER BY installed_rank DESC LIMIT 5;"

# Apply new migration (Flyway will auto-detect V41)
# Your existing Flyway setup should handle this
# OR manually apply:
docker-compose exec postgres psql -U postgres -d postgres -f /path/to/V41__add_goalie_gaa_to_features.sql
```

#### Verification
```sql
-- Verify columns were added
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'game_features'
  AND column_name LIKE '%goalie_gaa%';

-- Should return:
-- home_goalie_gaa | numeric(4,2)
-- away_goalie_gaa | numeric(4,2)
```

---

### **Session 4: Populate Goalie GAA (2-3 hours)**
**When:** Weekend 4
**Goal:** Create ETL script to populate goalie GAA into game_features

#### What You'll Build
`pipelines/etl/update_game_features_goalie_gaa.py`

#### Similar Script Reference
`pipelines/etl/update_game_features_goalies.py`
- Lines 30-80: Pattern for joining game_features with goalie_stats
- Lines 50-65: Logic for finding goalie stats "as of" a game date
- Lines 85-100: UPDATE statement with error handling

#### Key Differences from Existing Script
```python
# Existing update_game_features_goalies.py uses save_pct (which is NULL):
# SELECT gs.save_pct FROM goalie_stats gs ...

# Your new script uses gaa instead:
# SELECT gs.gaa FROM goalie_stats gs ...
```

#### The Logic
```python
# For each game:
# 1. Find the starting home goalie (from game_goalies table)
# 2. Look up that goalie's GAA as of game_date from goalie_stats
# 3. UPDATE game_features SET home_goalie_gaa = value
# 4. Repeat for away goalie

# Key challenge: "as of game_date"
# You want the goalie's GAA at the time of the game,
# not their season average calculated after season ends
```

#### Important Query Pattern
```sql
-- Get goalie GAA as of specific date
SELECT gs.gaa
FROM goalie_stats gs
WHERE gs.goalie_id = 'goalie_xyz'
  AND gs.game_date <= '2026-01-15'  -- "as of" date
ORDER BY gs.game_date DESC
LIMIT 1;
```

#### Structure
```python
# 1. Get all games that need goalie GAA populated
query_games = """
    SELECT gf.game_id, gf.game_date,
           gg.home_goalie_id, gg.away_goalie_id
    FROM game_features gf
    JOIN game_goalies gg ON gf.game_id = gg.game_id
    WHERE gf.home_goalie_gaa IS NULL
    ORDER BY gf.game_date
"""

# 2. For each game, look up goalie GAA
for game in games:
    home_gaa = get_goalie_gaa_as_of(game.home_goalie_id, game.game_date)
    away_gaa = get_goalie_gaa_as_of(game.away_goalie_id, game.game_date)

    # 3. UPDATE game_features
    update_query = """
        UPDATE game_features
        SET home_goalie_gaa = %s,
            away_goalie_gaa = %s
        WHERE game_id = %s
    """
    execute(update_query, (home_gaa, away_gaa, game.game_id))
```

#### Edge Cases
- Rookie goalie with no history: Use league average (~2.80 GAA)
- Backup goalie starting: Use their limited stats (may be noisy)
- Goalie change mid-season: Use most recent GAA, not season average

#### Verification
```bash
# Run the script
python -m pipelines.etl.update_game_features_goalie_gaa

# Check coverage
python -c "
import psycopg
from pipelines.config import DATABASE_URL

with psycopg.connect(DATABASE_URL) as conn:
    result = conn.execute('''
        SELECT
            COUNT(*) as total,
            COUNT(home_goalie_gaa) as has_gaa,
            ROUND(100.0 * COUNT(home_goalie_gaa) / COUNT(*), 1) as coverage_pct
        FROM game_features
        WHERE game_date >= '2023-10-01'
    ''').fetchone()
    print(f'GAA Coverage: {result[2]}% ({result[1]}/{result[0]} games)')
"

# Target: >90% coverage
```

---

### **Session 5: Train Enhanced Model (2-3 hours)**
**When:** Weekend 5
**Goal:** Retrain model with ELO + rest days + goalie GAA

#### What You'll Build
`pipelines/analysis/train_with_features.py`

#### Similar Script Reference
`pipelines/analysis/train_baseline_model.py` ← COPY THIS ENTIRELY
- This is your template - start by copying it 100%
- You'll only modify ~20 lines

#### The Changes You'll Make

**1. Update SQL Query (lines ~70-90):**
```python
# OLD (baseline):
query = """
    SELECT
        game_id,
        home_elo - away_elo as elo_diff,
        CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
    FROM game_features
    WHERE home_elo IS NOT NULL
"""

# NEW (with features):
query = """
    SELECT
        game_id,
        home_elo - away_elo as elo_diff,
        home_rest_days - away_rest_days as rest_diff,
        home_goalie_gaa - away_goalie_gaa as goalie_gaa_diff,
        CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
    FROM game_features
    WHERE home_elo IS NOT NULL
      AND home_rest_days IS NOT NULL
      AND away_rest_days IS NOT NULL
      AND home_goalie_gaa IS NOT NULL
      AND away_goalie_gaa IS NOT NULL
    -- Note: More restrictive WHERE clause reduces sample size
"""
```

**2. Update Feature Matrix (lines ~95-100):**
```python
# OLD:
X = df[['elo_diff']]

# NEW:
X = df[['elo_diff', 'rest_diff', 'goalie_gaa_diff']]
```

**3. Update Feature Names for Logging (lines ~120-130):**
```python
# Add this for debugging:
print("\nFeature Importance (if using linear model):")
if hasattr(model, 'coef_'):
    features = ['elo_diff', 'rest_diff', 'goalie_gaa_diff']
    for feat, coef in zip(features, model.coef_[0]):
        print(f"  {feat}: {coef:.4f}")
```

#### Expected Results

**Success Criteria** (from `FEATURE_ENGINEERING_TODO.md`):
- Accuracy improvement: **>0.5%** (55.0% → 55.5%+)
- Brier score decrease: **>0.01** (0.248 → 0.238)
- Calibration error decrease: **>1%** (4.0% → 3.0%)

**If you hit ANY of these thresholds, the features are worth adding!**

#### Interpretation Guide
```python
# Example feature coefficients from logistic regression:
# elo_diff:        +0.0234  (higher ELO → more likely to win)
# rest_diff:       +0.1200  (more rest → more likely to win)
# goalie_gaa_diff: -0.5000  (opponent's GAA higher → more likely to win)

# Signs matter:
# - Positive = feature increases win probability
# - Negative = feature decreases win probability
# - Magnitude = strength of effect
```

#### Red Flags
- ❌ Accuracy DECREASES → Features are adding noise, not signal
- ❌ Brier score INCREASES → Worse probabilistic predictions
- ❌ Feature coefficient signs are backwards (e.g., rest_diff is negative)
- ❌ Sample size drops dramatically (check WHERE clause conditions)

---

### **Session 6: Retrain Calibration (2 hours)**
**When:** Weekend 6
**Goal:** Train new Platt scaling for Phase 2 model

#### What You'll Do
Run existing script with new model predictions!

#### Similar Script Reference
`pipelines/analysis/train_platt_scaling.py` ← Already exists, just run it!

#### The Process
```bash
# 1. Train enhanced model (from Session 5)
python -m pipelines.analysis.train_with_features

# Output:
# - Saves model to database or pickle file
# - Reports test set metrics

# 2. Train new Platt scaling
python -m pipelines.analysis.train_platt_scaling

# This will:
# - Load the new model
# - Fit Platt parameters on validation set
# - Save new params to calibration_params table
# - Report calibration improvement
```

#### Understanding the Results

**Compare Old vs New Parameters:**
```sql
-- View all calibration parameters
SELECT
    param_id,
    param_name,
    param_a,
    param_b,
    created_at,
    is_active
FROM calibration_params
ORDER BY param_id;

-- You should see:
-- param_id=3: ELO-only (a=0.1977, b=0.0353) - Phase 1
-- param_id=5: With features (a=?, b=?) - Phase 2 (NEW)
```

**What to Look For:**

**Param A (compression factor):**
- Old: a=0.1977 (extreme compression)
- **Hope:** a=0.5-0.7 (less compression needed)
- **Why:** Better features → model naturally more accurate → less calibration needed

**Param B (bias shift):**
- Old: b=0.0353 (slight upward shift)
- **Hope:** b closer to 0 (less bias)

**Calibration Error:**
- Old: 4.03% (Phase 1)
- **Target:** <3.0% (Phase 2)

#### Example Good Outcome
```
Phase 1 (ELO only):
- Raw calibration: 18.77% error
- Platt scaling: a=0.1977, b=0.0353
- Final calibration: 4.03% error

Phase 2 (ELO + rest + goalie):
- Raw calibration: 8.50% error  ← BETTER starting point!
- Platt scaling: a=0.6500, b=0.0100  ← Less compression needed
- Final calibration: 2.10% error  ← BETTER final result!
```

#### Activation Decision
**DO NOT activate new parameters yet!**
- Save them to database (param_id=5)
- Mark as `is_active = FALSE`
- You'll activate in September after paper trading validation

---

## 📅 Realistic Timeline

| Week | Session | Milestone | Cumulative Hours |
|------|---------|-----------|------------------|
| **Week 1** | Session 1 | Rest days calculated ✅ | 2-3 hrs |
| **Week 2** | Session 2 | Rest days verified ✅ | 3-4 hrs |
| **Week 3** | Session 3 | Goalie GAA schema ready ✅ | 5-6 hrs |
| **Week 4** | Session 4 | Goalie data populated ✅ | 8-9 hrs |
| **Week 5** | Session 5 | Enhanced model trained ✅ | 10-12 hrs |
| **Week 6** | Session 6 | New calibration complete ✅ | 12-15 hrs |

**Target Completion:** Mid-July 2026
**Buffer Time:** July-August for testing/refinement
**September:** Paper trading with preseason games
**October:** Launch Phase 2 for 2026-27 season

---

## 🎓 Learning Mode: How We'll Work Together

For each session:

1. **I give you hints** (reference scripts, key patterns)
2. **You try implementing** - write code yourself, struggle is part of learning
3. **You share your work** - code, errors, questions
4. **I review and guide** - point out issues, explain why, suggest fixes
5. **You iterate** - apply feedback, improve
6. **We validate** - test it actually works and improves model

**This way you learn by doing, not just copying.**

---

## 📋 Success Metrics

### Phase 2 Model Targets

| Metric | Phase 1 (Baseline) | Phase 2 (Target) | Improvement |
|--------|-------------------|------------------|-------------|
| **Accuracy** | 54.98% | >56% | +1%+ |
| **Calibration** | 4.03% | <3% | -25%+ |
| **Brier Score** | 0.2473 | <0.240 | -3%+ |
| **Probability Range** | 47-54% | 40-60% | Less compression |

### Minimum Success Criteria
**Must achieve at least ONE of:**
- ✅ Accuracy +0.5% or more
- ✅ Calibration -1% or more
- ✅ Brier -0.01 or more

**If none of these are met, features aren't helping.**

---

## 🚨 Red Flags & What to Do

### During Development

**🔴 Coverage <80% after ETL run**
- **Problem:** Query missing many games or data source incomplete
- **Action:** Debug SQL query, check for NULL values in source tables

**🔴 Model accuracy DECREASES with new features**
- **Problem:** Features are noise, not signal
- **Action:** Test features individually, remove the problematic ones

**🔴 Feature coefficient signs are backwards**
- **Problem:** Logic error in feature calculation (e.g., rest_diff = away - home instead of home - away)
- **Action:** Fix the differential calculation

**🔴 Sample size drops >30% with new features**
- **Problem:** Too many NULL values, restrictive WHERE clause
- **Action:** Improve feature coverage before training

### After Validation

**🔴 Paper trading performance much worse than backtest**
- **Problem:** Data leakage in training or distribution shift
- **Action:** Review feature engineering for look-ahead bias

**🔴 Calibration drifts >3% in live testing**
- **Problem:** Model not generalizing or overfitting to validation set
- **Action:** Retrain with different data split, add regularization

---

## 🗂️ File Organization

### New Files You'll Create
```
pipelines/
  etl/
    calculate_rest_days.py          ← Session 1
    update_game_features_goalie_gaa.py  ← Session 4
  analysis/
    train_with_features.py          ← Session 5

infra/db/migrations/
  V41__add_goalie_gaa_to_features.sql  ← Session 3
```

### Files You'll Reference
```
pipelines/
  etl/
    update_game_features_elos.py    ← Pattern for Session 1
    update_game_features_goalies.py ← Pattern for Session 4
    calculate_goalie_stats.py       ← GAA source data
  analysis/
    train_baseline_model.py         ← Template for Session 5
    train_platt_scaling.py          ← Run in Session 6
    diagnose_rest_days_coverage.py  ← Use in Session 2
```

---

## 🎯 Post-Roadmap: September Validation

After completing all 6 sessions, you'll have a Phase 2 model ready for testing.

### September Paper Trading Plan

**Week 1 (Sept 1-7): Preseason Warmup**
```bash
# Run daily during preseason games
python -m pipelines.pricing.compute_game_pricing_elos
python -m pipelines.pricing.compute_edges
python -m pipelines.betting.select_paper_bets
```

**Week 2-3 (Sept 8-21): Monitor Performance**
```sql
-- Daily calibration check
SELECT
    COUNT(*) as num_bets,
    AVG(model_prob) as avg_predicted,
    AVG(CASE WHEN bet_status = 'won' THEN 1.0 ELSE 0.0 END) as actual_win_rate,
    ABS(AVG(model_prob) - AVG(CASE WHEN bet_status = 'won' THEN 1.0 ELSE 0.0 END)) as calibration_error
FROM bet_log
WHERE is_paper_money = TRUE
  AND created_at >= NOW() - INTERVAL '7 days'
  AND bet_status IN ('won', 'lost');
```

**Week 4 (Sept 22-30): Activate Decision**
- If calibration <5% and ROI positive → Activate Phase 2 for real money
- If performance worse than Phase 1 → Keep Phase 1 active, debug Phase 2

**October 1:** Season starts! 🏒

---

## 💪 Getting Started

### Your First Task (Start This Weekend)

**Session 1: Rest Days Feature**

**Step 1: Study the Pattern (15 min)**
```bash
# Read the ELO update script
code pipelines/etl/update_game_features_elos.py

# Focus on:
# - Lines 40-120: How it iterates through games
# - Lines 80-95: UPDATE syntax
# - Lines 15-30: Database setup
```

**Step 2: Plan Your Logic (15 min)**
Write pseudocode on paper:
```
For each game:
  1. Find home team's previous game (WHERE date < current_date)
  2. Calculate days_since = current_date - previous_date
  3. UPDATE game_features SET home_rest_days = days_since
  4. Repeat for away team
  5. Handle edge case: first game of season = NULL
```

**Step 3: Write the Script (90 min)**
Create `pipelines/etl/calculate_rest_days.py`

**Step 4: Test Small (15 min)**
```bash
# Test on one team first
python -m pipelines.etl.calculate_rest_days --team "BOS" --limit 10
```

**Step 5: Full Run & Verify (15 min)**
```bash
python -m pipelines.etl.calculate_rest_days
python -m pipelines.analysis.diagnose_rest_days_coverage
```

---

## 📞 Getting Help

When you get stuck:

1. **Share what you tried** - show your code or describe the issue
2. **Show the error message** - full stack trace helps
3. **Explain what you expected** vs what happened
4. **Ask specific questions** - "How do I X?" is better than "It's broken"

I'm here to guide, not do it for you. The struggle is part of learning!

---

## 📚 Related Documentation

**Keep These Handy:**
- `FEATURE_ENGINEERING_TODO.md` - Feature priority and success criteria
- `DATA_SPLIT_STRATEGY.md` - How to split data for training
- `SUCCESS_METRICS.md` - Performance targets
- `PAPER_TRADING.md` - September validation system
- `DEV_WORKFLOW.md` - Docker + local development patterns

**Archived (Reference Only):**
- `archive_2025_26_season/PHASE_1_RESULTS.md` - Phase 1 baseline performance
- `archive_2025_26_season/DEPLOYMENT_CHECKLIST.md` - Phase 1 deployment steps

---

## ✅ Checklist: Before Starting

- [ ] Read this entire roadmap document
- [ ] Understand the 6-session structure
- [ ] Review `FEATURE_ENGINEERING_TODO.md` for context
- [ ] Set aside 2-3 hours for Session 1 this weekend
- [ ] Docker environment working (`nhl-start` command)
- [ ] Can connect to database (`dpsql` works)
- [ ] Have your IDE ready (VSCode/IntelliJ)

**Once ready, ping me and we'll start Session 1!** 🚀

---

**Created:** June 1, 2026
**Last Updated:** June 1, 2026
**Next Review:** After completing Session 6 (mid-July 2026)
**Owner:** Nathan (with AI guidance in Learning Mode)
