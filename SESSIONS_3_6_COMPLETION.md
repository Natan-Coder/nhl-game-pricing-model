# Sessions 3-6 Completion Summary

**Date:** June 24-25, 2026
**Objective:** Complete Phase 2 model enhancement with goalie GAA and rest days features
**Status:** ✅ All sessions complete, ⚠️ Results below expectations

---

## Session 3: Goalie GAA Schema Setup

### Objective
Add `home_goalie_gaa` and `away_goalie_gaa` columns to `game_features` table.

### What We Built
**Migration:** `infra/db/migrations/V41__add_goalie_gaa_to_features.sql`

**Design Decisions:**
- **Data Type:** `NUMERIC(4,2)` - Supports GAA range 0.00 to 99.99
- **NULL Handling:** Allow NULL (honest approach - don't impute fake data)
- **Indexing:** Partial index on `game_id WHERE home_goalie_gaa IS NOT NULL`

**Key Learning:**
- Discussed NULL vs default value tradeoff
- Chose NULL for ML integrity (real data > imputed data)
- Partial indexes save space and improve query performance

### Results
- ✅ Migration created and applied to Supabase production
- ✅ Columns added successfully
- ✅ Initial coverage: 0% (as expected - data populated in Session 4)

**Time Spent:** ~20 minutes (estimated 2 hours - crushed it!)

---

## Session 4: Populate Goalie GAA Data

### Objective
Create ETL script to populate goalie GAA columns from `goalie_stats` table.

### What We Built
**Script:** `pipelines/etl/update_game_features_goalie_gaa.py` (56 lines)

**Pattern Used:**
- Copied structure from `update_game_features_goalies.py`
- Modified to use `gaa` column instead of `save_pct`
- 3-table JOIN: `game_features` → `game_goalies` → `goalie_stats`

**SQL Logic:**
```sql
UPDATE game_features gf
SET
    home_goalie_gaa = home_gs.gaa,
    away_goalie_gaa = away_gs.gaa
FROM game_goalies gg
LEFT JOIN goalie_stats home_gs
    ON home_gs.goalie_id = gg.home_goalie_id
    AND home_gs.season = SUBSTRING(gg.game_id::text, 1, 4)::int  -- Match season!
```

**Key Learning:**
- Multi-table JOINs for ETL
- Season extraction from game_id (`2025020999` → `2025`)
- NULL handling with LEFT JOIN

### Results
- ✅ **4,060 games updated** (95.4% coverage)
- ✅ **Target exceeded:** >90% goal achieved
- ✅ **Data quality verified:** GAA avg 2.97 (realistic!)
- ✅ **Distribution healthy:** Min 1.00, Max 6.00

**Sample Data:**
```
DET vs MIN | Home GAA: 2.88, Away GAA: 3.17
PIT vs FLA | Home GAA: 3.65, Away GAA: 2.81
```

**Time Spent:** ~30 minutes (estimated 2-3 hours)

---

## Session 5: Train Enhanced Model

### Objective
Train logistic regression with ELO + rest days + goalie GAA features.

### What We Built
**Script:** `pipelines/analysis/train_with_features.py` (152 lines)

**Features Used:**
1. `elo_diff` = `home_elo - away_elo`
2. `rest_diff` = `home_rest - away_rest`
3. `goalie_gaa_diff` = `home_goalie_gaa - away_goalie_gaa`

**SQL Query:**
```sql
SELECT
    gf.home_elo - gf.away_elo as elo_diff,
    gf.home_rest - gf.away_rest as rest_diff,
    gf.home_goalie_gaa - gf.away_goalie_gaa as goalie_gaa_diff,
    CASE WHEN gr.home_goals > gr.away_goals THEN 1 ELSE 0 END as home_win
FROM game_features gf
WHERE gf.home_elo IS NOT NULL
  AND gf.home_rest IS NOT NULL
  AND gf.home_goalie_gaa IS NOT NULL
```

**Key Learning:**
- How to adapt baseline model template
- Adding multiple features to logistic regression
- Importance of NULL filtering for complete feature sets

### Results

**Test Set Performance:**
- **Accuracy:** 55.19% (target: >55.48%)
- **Brier Score:** 0.2467 (target: <0.2373)
- **Calibration Error:** 20.10% (raw, before Platt scaling)

**Feature Importance (Coefficients):**
```
elo_diff:         +0.0056  ⭐ Strong positive (higher ELO = more wins)
rest_diff:        -0.0002  ❌ NEARLY ZERO (rest days don't help!)
goalie_gaa_diff:  -0.0744  ✅ Moderate (opponent worse goalie = more wins)
```

**Key Findings:**
- ❌ **Rest days feature FAILED** - coefficient -0.0002 is essentially zero
- ✅ **Goalie GAA helped** - but not enough to meet +0.5% accuracy threshold
- ⚠️ **Accuracy improved +0.21%** - below +0.5% target

**Time Spent:** ~45 minutes (estimated 2-3 hours)

---

## Session 6: Train Platt Scaling

### Objective
Calibrate enhanced model probabilities using Platt scaling.

### What We Built
**Modified:** `pipelines/analysis/train_platt_scaling.py`

**Changes Made:**
1. Updated `load_data()` to include all 3 features
2. Rewrote `train_and_predict()` to train enhanced model inline
3. Updated log messages for enhanced model

**Platt Scaling Process:**
1. Train enhanced model on training set
2. Generate predictions on validation set
3. Fit parameters: `calibrated_prob = sigmoid(a * logit(raw_prob) + b)`
4. Evaluate on test set

**Key Learning:**
- How Platt scaling fixes calibration
- Parameter interpretation (compression vs shift)
- Integration of calibration with model training

### Results

**Platt Parameters:**
- **a = 0.1726** (strong compression toward 50%)
- **b = 0.0608** (slight upward shift)
- **Saved as param_id = 7** in database

**Calibration Improvement:**
- **Before Platt:** 20.10% error
- **After Platt:** 9.13% error
- **Improvement:** +10.97% ✅

**Example Transformations:**
```
Raw 35% → Calibrated 48.8%  (+13.8%)
Raw 40% → Calibrated 49.8%  (+9.8%)
Raw 50% → Calibrated 51.5%  (+1.5%)
Raw 60% → Calibrated 53.3%  (-6.7%)
Raw 65% → Calibrated 54.2%  (-10.8%)
```

**Key Findings:**
- ✅ Platt scaling improved calibration significantly
- ❌ **Still at 9.13% error** (target: <3%)
- ❌ **Probabilities compressed to 48-54% range** (same issue as Phase 1!)
- ⚠️ **Worse than Phase 1** (4.03% → 9.13%)

**Time Spent:** ~30 minutes (estimated 2 hours)

---

## Overall Phase 2 Results

### Comparison to Phase 1 Baseline

| Metric | Phase 1 (ELO only) | Phase 2 (Enhanced) | Change | Target Met? |
|--------|-------------------|-------------------|---------|-------------|
| **Accuracy** | 54.98% | 55.19% | +0.21% | ❌ (needed +0.5%) |
| **Brier Score** | 0.2473 | 0.2467 | -0.0006 | ❌ (needed -0.01) |
| **Calibration (Raw)** | 18.77% | 20.10% | +1.33% | ❌ Worse |
| **Calibration (Platt)** | 4.03% | 9.13% | +5.10% | ❌ Worse |
| **Prob Range** | 47-54% | 48-54% | Similar | ❌ Still compressed |

### Success Criteria (from OFFSEASON_2026_ROADMAP.md)

**Must meet at least ONE:**
- ❌ Accuracy +0.5% or more (got +0.21%)
- ❌ Brier -0.01 or more (got -0.0006)
- ❌ Calibration -1% or more (got +5.10% - WORSE!)

**Verdict:** Phase 2 model did NOT meet success criteria.

---

## What Went Wrong?

### 1. Rest Days Feature Failed Completely
- **Coefficient:** -0.0002 (essentially zero)
- **Expected:** Positive coefficient (more rest = better performance)
- **Reality:** Feature added no predictive power

**Possible Reasons:**
- NHL scheduling already optimized (all teams manage rest similarly)
- Back-to-backs accounted for in ELO updates
- Data quality issues?
- Feature engineering problem?

### 2. Goalie GAA Helped, But Not Enough
- **Coefficient:** -0.0744 (moderate strength)
- **Expected:** Significant predictor
- **Reality:** Marginal improvement

**Possible Reasons:**
- GAA is season-level aggregate (data leakage concerns)
- Top goalies already on top teams (correlated with ELO)
- Save percentage might be better metric
- Need game-by-game goalie performance, not season average

### 3. Calibration Got Worse
- **Phase 1:** 4.03% (excellent!)
- **Phase 2:** 9.13% (poor)

**Why?**
- Adding weak features increased model uncertainty
- Probability compression persists (48-54% range)
- Model fundamentally lacks discriminative power
- Additional features created noise, not signal

---

## Key Learnings

### Technical Skills Gained
1. ✅ **ETL Pipeline Development** - Multi-table JOINs, NULL handling
2. ✅ **Feature Engineering** - Creating differential features
3. ✅ **Model Training** - Multi-feature logistic regression
4. ✅ **Calibration Techniques** - Platt scaling implementation
5. ✅ **SQL & Database** - Migrations, indexing, query optimization
6. ✅ **Python & Pandas** - Data loading, processing, model evaluation

### ML/Data Science Lessons
1. ⚠️ **More features ≠ better model** - Rest days added nothing
2. ⚠️ **Domain knowledge matters** - Not all "logical" features work
3. ⚠️ **Calibration is hard** - Compression suggests fundamental model limitation
4. ⚠️ **Data quality critical** - Season-level GAA may not be granular enough
5. ✅ **Feature importance reveals truth** - Coefficients showed rest_diff useless
6. ✅ **Validation prevents overfitting** - Test set showed real performance

---

## Total Time Investment

| Session | Estimated | Actual | Efficiency |
|---------|-----------|--------|------------|
| Session 3 | 2 hours | 20 min | 6x faster ✅ |
| Session 4 | 2-3 hours | 30 min | 5x faster ✅ |
| Session 5 | 2-3 hours | 45 min | 3x faster ✅ |
| Session 6 | 2 hours | 30 min | 4x faster ✅ |
| **Total** | **8-10 hours** | **~2 hours** | **4-5x faster** ✅ |

**Why so fast?**
- Learning mode with guidance
- Copy-paste-modify workflow
- Understanding patterns vs writing from scratch
- Focused scope (no rabbit holes)

---

## Files Created/Modified

### New Files
- `infra/db/migrations/V41__add_goalie_gaa_to_features.sql` (61 lines)
- `pipelines/etl/update_game_features_goalie_gaa.py` (56 lines)
- `pipelines/analysis/train_with_features.py` (152 lines)

### Modified Files
- `pipelines/analysis/train_platt_scaling.py` (updated for enhanced model)

### Total Lines of Code
- **~330 lines** written across 4 files
- All working, tested, and documented

---

## Next Steps (Investigation Phase)

### Immediate Questions to Answer
1. **Why did rest days fail?**
   - Data quality check
   - Distribution analysis
   - Correlation with outcomes

2. **Can we improve goalie features?**
   - Use save percentage instead of GAA?
   - Game-by-game stats instead of season average?
   - Recent form (last 10 games) vs season?

3. **Why is calibration so bad?**
   - Model structure issue?
   - Insufficient features?
   - NHL betting markets too efficient?

4. **Is Phase 2 worth deploying?**
   - +0.21% accuracy improvement
   - But worse calibration (9.13% vs 4.03%)
   - Complexity added for minimal gain

### Investigation Plan
1. Analyze rest days data distribution
2. Examine goalie GAA feature effectiveness
3. Compare Phase 1 vs Phase 2 in detail
4. Explore calibration compression root cause
5. Document recommendations for future work

---

## Conclusion

**Sessions 3-6 were a SUCCESS as a learning experience**, but the model results were **disappointing**:

✅ **Learning Objectives:** Achieved
✅ **Technical Execution:** Flawless
❌ **Model Performance:** Below expectations
❌ **Deployment Readiness:** Not recommended

**This is real ML work** - not every experiment succeeds. The important part is understanding **why** it failed and learning from it.

**Recommendation:** Stick with Phase 1 (ELO-only) model for production. Investigate further before attempting Phase 2 deployment.

---

**Created:** June 25, 2026
**Last Updated:** June 25, 2026
**Status:** Investigation phase beginning
