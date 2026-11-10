# NHL Betting Model - Project Status

**Last Updated:** June 25, 2026
**Current Phase:** Phase 2 Investigation Complete - Recommendation: Use Phase 1 for 2026-27
**Model Version:** Phase 1 (ELO + Platt Scaling v1.0) - **Recommended for Production**

---

## 🎯 Quick Summary

**Phase 1 ELO-based model is the recommended production model** for the 2026-27 season.

Phase 2 enhancement (adding rest days + goalie GAA features) was completed and investigated but **did not meet success criteria**. While it improved accuracy marginally (+0.21%), it significantly degraded calibration (4.03% → 9.13%), making it unsuitable for production use.

**Phase 1 Performance (2025-26 Season):**
- ✅ Accuracy: 54.98% (target: >53%)
- ✅ Calibration: 4.03% (target: <5%)
- ✅ Brier Score: 0.2473 (target: <0.250)

**Phase 2 Performance (Investigation Complete):**
- ⚠️ Accuracy: 55.19% (+0.21%, target was +0.5%)
- ❌ Calibration: 9.13% (+5.10%, target was -1%)
- ⚠️ Brier Score: 0.2467 (-0.0006, target was -0.01)

**Decision:** Deploy Phase 1 for 2026-27 season. Phase 2 features did not provide meaningful improvement.

---

## 📋 Phase 2 Investigation Summary

**Date:** June 24-25, 2026
**Status:** ✅ All 6 sessions complete + comprehensive investigation
**Time Invested:** ~2 hours (vs 8-10 hour estimate)
**Result:** Phase 2 **NOT recommended** for deployment

### What We Built

**Sessions 3-6 (June 24-25, 2026):**
- ✅ Migration V41: Goalie GAA schema (20 min)
- ✅ `update_game_features_goalie_gaa.py`: Populated 4,060 games (30 min)
- ✅ `train_with_features.py`: Enhanced model training (45 min)
- ✅ Modified `train_platt_scaling.py`: Calibration for enhanced model (30 min)

**Total:** ~330 lines of working, tested code

### Why Phase 2 Failed

**1. Rest Days Feature: Complete Failure**
- Coefficient: -0.0002 (essentially zero)
- Correlation with wins: -0.0246 (very weak)
- NHL scheduling is already balanced (50.9% equal rest)
- Data quality issues (cross-season calculation bugs)
- **Conclusion:** Useless for prediction

**2. Goalie GAA Feature: Minimal Impact**
- Coefficient: -0.0744 (moderate but weak)
- Correlation with wins: -0.0093 (weaker than rest days!)
- Season-level aggregation too coarse
- Data leakage concerns (includes future games)
- **Conclusion:** Minimal value added

**3. Calibration Degradation**
- Phase 1: 4.03% error ✅
- Phase 2: 9.13% error ❌ (127% worse!)
- Weak features added noise, not signal
- Model became less confident (appropriately)
- **Conclusion:** Unacceptable for betting

### Key Documentation

**Investigation Documents (June 25, 2026):**
- `SESSIONS_3_6_COMPLETION.md` - Full session summary and results
- `PHASE_1_VS_PHASE_2_COMPARISON.md` - Side-by-side performance analysis
- `CALIBRATION_COMPRESSION_ANALYSIS.md` - Root cause of probability compression
- `PHASE_2_RECOMMENDATIONS.md` - **Final recommendations and next steps**

**Recommendation:** Read `PHASE_2_RECOMMENDATIONS.md` for complete analysis and path forward.

---

## 🧪 Paper Trading System

**Status:** Deployed April 24, 2026 - Ready for Use

A parallel testing system that validates strategies with simulated money before risking real capital.

**Key Features:**
- Separate $1,000 paper bankroll
- Same strategies and edge calculations as real money
- Track both real and paper bets in parallel
- Compare performance side-by-side

**Database Changes:**
- ✅ V39: Added `is_paper_money` column to `bet_log`
- ✅ V40: Created `paper_bankroll_state` table
- ✅ V41: Added goalie GAA columns (Phase 2 investigation)

**Current State:**
- Paper Bankroll: $1,000.00
- Paper Bets Placed: 0 (ready for 2026-27 season)

**See:** `PAPER_TRADING.md` for full documentation

---

## 📂 Key Documentation Files

**Phase 2 Investigation (START HERE):**
| File | Purpose | Read This If... |
|------|---------|-----------------|
| **`PHASE_2_RECOMMENDATIONS.md`** | Final decision & next steps | 🔥 **START HERE** - Complete analysis |
| **`PHASE_1_VS_PHASE_2_COMPARISON.md`** | Performance comparison | Understanding why Phase 1 wins |
| **`CALIBRATION_COMPRESSION_ANALYSIS.md`** | Root cause analysis | Understanding probability compression |
| **`SESSIONS_3_6_COMPLETION.md`** | What we built | Session-by-session details |

**Core Documentation:**
| File | Purpose | Read This If... |
|------|---------|-----------------|
| **`README.md`** | Project overview | You're new to the project |
| **`PAPER_TRADING.md`** | Paper trading system | Testing strategies safely |
| **`DEV_WORKFLOW.md`** | Development workflow | Setting up dev environment |
| **`DATA_SPLIT_STRATEGY.md`** | Train/val/test methodology | Training models properly |
| **`SUCCESS_METRICS.md`** | Performance targets | Understanding validation criteria |

**Phase 1 (Archived - Successful):**
| File | Purpose |
|------|---------|
| `archive_2025_26_season/PHASE_1_RESULTS.md` | Phase 1 performance analysis |
| `archive_2025_26_season/DEPLOYMENT_CHECKLIST.md` | Phase 1 deployment guide |
| `archive_2025_26_season/FINAL_MODEL_CONFIGURATION.md` | Phase 1 configuration |

**Phase 2 (Archived - Not Deployed):**
| File | Purpose |
|------|---------|
| `OFFSEASON_2026_ROADMAP.md` | Original Phase 2 plan (completed) |
| `FEATURE_ENGINEERING_TODO.md` | Feature analysis (investigated) |

---

## 🚀 Next Steps (2026-27 Season)

### July-August 2026: Preparation

**Week 1 (Now):**
- ✅ Complete Phase 2 investigation
- ✅ Document findings and recommendations
- ⏳ Update all project documentation
- ⏳ Archive Phase 2 code

**Weeks 2-8:**
- Monitor any remaining 2025-26 season games
- Prepare infrastructure for new season
- Review and optimize betting thresholds
- Plan paper trading for preseason

### September 2026: Preseason Validation

**Preseason Games (Sept 1-21):**
- Run Phase 1 model on preseason games
- Paper trade with simulated money
- Verify calibration holds
- Confirm data pipelines working
- Test any infrastructure changes

**Target Metrics:**
- Calibration <7% (allow for small sample noise)
- ROI positive (but preseason has different dynamics)
- No pipeline failures

### October 2026: Season Launch

**2026-27 Season (Starts Oct 1):**
- Deploy Phase 1 model for real/paper betting
- Use Phase 1 Platt parameters (a=0.1977, b=0.0353, param_id=3)
- Monitor calibration weekly
- Track performance vs baseline
- Continue paper trading in parallel

**Success Criteria:**
- Calibration <5%
- ROI >5%
- Sharpe ratio >1.5
- Max drawdown <20%

---

## 📊 What We Have

### Phase 1: ELO-Only Model (PRODUCTION READY ✅)

**Features:**
- Single feature: ELO rating differential (`home_elo - away_elo`)
- Logistic regression classifier
- Platt scaling calibration (a=0.1977, b=0.0353)

**Data:**
- Training: 2,807 games (2023-24 + partial 2024-25)
- Validation: 637 games (1st half 2025-26)
- Test: 712 games (2nd half 2025-26)

**Performance:**
- **Accuracy:** 54.98% ✅
- **Calibration:** 4.03% ✅ (best we can achieve with public data)
- **Brier Score:** 0.2473 ✅
- **Probability Range:** 47-55% (compressed but well-calibrated)

**Why It's the Best Option:**
- Superior calibration quality
- Simpler to maintain
- More test data (no feature filtering)
- Already validated in production
- Reflects true NHL parity and market efficiency

### Phase 2: Enhanced Model (NOT RECOMMENDED ❌)

**Features:**
- `elo_diff` + `rest_diff` + `goalie_gaa_diff`

**Performance:**
- **Accuracy:** 55.19% (+0.21% improvement)
- **Calibration:** 9.13% ❌ (127% worse than Phase 1!)
- **Brier Score:** 0.2467 (negligible improvement)
- **Sample Size:** 511 games (28% data loss from filtering)

**Why Not Deployed:**
- Calibration degradation is critical for betting
- Marginal accuracy gain doesn't offset calibration loss
- Added complexity without meaningful value
- Lost 28% of test data to missing features

---

## 🎓 Key Learnings

### From Phase 2 Investigation

**What We Learned:**
1. **More features ≠ better model** - Can add noise instead of signal
2. **NHL parity is fundamental** - Can't be "fixed" with features
3. **Calibration > accuracy** - For betting, accurate probabilities matter most
4. **Market efficiency is real** - Public data has limited edge
5. **Test assumptions with data** - Rest days "should" matter but don't
6. **Simpler is often better** - Occam's Razor applies to ML

### Technical Skills Acquired

**From Sessions 3-6:**
- ETL pipeline development (multi-table JOINs, NULL handling)
- Feature engineering and validation
- Model comparison methodology
- Calibration techniques (Platt scaling)
- Root cause analysis for ML failures
- Professional ML documentation

### The NHL Parity Problem

**Why NHL is Hard to Predict:**
- Salary cap creates team parity
- 50% of teams make playoffs (competitive incentives)
- High variance sport (goalies, bounces, small samples)
- Efficient betting markets (public info already priced in)

**Evidence:**
- ELO differentials cluster near zero (avg 0.55 points)
- Win rates only vary 42-62% across 200 ELO point range
- Both models compress probabilities to 47-55% range
- **This reflects reality, not model failure**

---

## 🔧 Project Structure

```
nhl-betting-model/
├── pipelines/
│   ├── analysis/
│   │   ├── train_baseline_model.py          ✅ Phase 1 training
│   │   ├── train_with_features.py           ✅ Phase 2 (not deployed)
│   │   ├── train_platt_scaling.py           ✅ Calibration training
│   │   ├── diagnose_goalie_coverage.py      ✅ Diagnostic tool
│   │   └── diagnose_rest_days_coverage.py   ✅ Diagnostic tool
│   ├── etl/
│   │   ├── update_game_features_elos.py     ✅ Populate ELO data
│   │   ├── calculate_rest_days.py           ✅ Rest days (99.4% coverage)
│   │   ├── update_game_features_goalie_gaa.py ✅ Goalie GAA (95.4% coverage)
│   │   ├── calculate_goalie_stats.py        ✅ Goalie stats calculation
│   │   └── replay_elos.py                   ✅ ELO backfill
│   ├── betting/
│   │   ├── select_bets.py                   ✅ Real money betting
│   │   ├── select_paper_bets.py             ✅ Paper money betting
│   │   ├── preview_edges.py                 ✅ Preview before betting
│   │   └── reports.py                       ✅ Betting reports
│   ├── pricing/
│   │   ├── compute_game_pricing_elos.py     ✅ Generate predictions
│   │   └── compute_edges.py                 ✅ Calculate edges (uses Platt)
│   └── common/
│       ├── data_splits.py                   ✅ Train/val/test logic
│       └── logging_setup.py                 ✅ Logging utilities
├── infra/
│   └── db/migrations/                       ✅ V1-V41 applied
├── docs/
│   ├── PHASE_2_RECOMMENDATIONS.md           🔥 **Read this**
│   ├── PHASE_1_VS_PHASE_2_COMPARISON.md     📘 Performance analysis
│   ├── CALIBRATION_COMPRESSION_ANALYSIS.md  📘 Root cause analysis
│   ├── SESSIONS_3_6_COMPLETION.md           📘 Session details
│   ├── PAPER_TRADING.md                     📘 Paper trading guide
│   ├── DATA_SPLIT_STRATEGY.md               📘 Data methodology
│   ├── SUCCESS_METRICS.md                   📘 Performance targets
│   └── PROJECT_STATUS.md                    📘 This file
└── README.md                                ℹ️ Project overview
```

---

## 📈 Success Criteria for 2026-27 Season

**Using Phase 1 Model:**

| Metric | Target | Alert If |
|--------|--------|----------|
| **Calibration Error** | <5% | >7% |
| **ROI** | >5% | <-5% |
| **Sharpe Ratio** | >1.5 | <1.0 |
| **Max Drawdown** | <20% | >25% |
| **Bet Volume** | >200 bets/season | <100 |

**Monthly Review:**
- Compare actual vs predicted win rates
- Check for calibration drift
- Evaluate bet selection criteria
- Adjust edge thresholds if needed

---

## 🐛 Known Limitations (Accepted)

### 1. Probability Compression (47-55% range)

**Status:** ✅ Accepted - Reflects NHL parity
- Raw model has good spread (27-78%)
- Platt scaling compresses to fix overconfidence
- This is appropriate given NHL market efficiency
- **Better to be accurately uncertain than confidently wrong**

### 2. Calibration Above Ideal (4.03% vs 3% target)

**Status:** ✅ Acceptable
- Meets <5% threshold
- Among best achievable with public data
- Phase 2 made it worse (9.13%)
- Not worth sacrificing for minor improvement

### 3. Limited Bet Opportunities

**Status:** ✅ Accepted - Focus on quality over quantity
- Narrow probability range limits edges
- Markets are efficient
- High edge threshold (>4%) reduces bet frequency
- **This is appropriate - only bet when truly +EV**

---

## 💾 Database Quick Reference

### Active Configuration

**Phase 1 Platt Scaling Parameters:**
```sql
SELECT * FROM calibration_params WHERE param_id = 3;
-- a = 0.1977
-- b = 0.0353
-- is_active = TRUE
```

**Phase 2 Platt Scaling Parameters (NOT ACTIVE):**
```sql
SELECT * FROM calibration_params WHERE param_id = 7;
-- a = 0.1726
-- b = 0.0608
-- is_active = FALSE (saved for reference only)
```

### Key Queries

```sql
-- Current ELO ratings
SELECT * FROM team_elo_history ORDER BY game_id DESC LIMIT 20;

-- Features for model training (with Phase 2 features)
SELECT
    game_id,
    home_elo - away_elo as elo_diff,
    home_rest - away_rest as rest_diff,
    home_goalie_gaa - away_goalie_gaa as goalie_gaa_diff
FROM game_features
WHERE game_date >= '2026-10-01'
  AND home_elo IS NOT NULL
LIMIT 10;

-- Live calibration check
SELECT
    AVG(model_prob) as avg_pred,
    AVG(CASE WHEN bet_status = 'won' THEN 1.0 ELSE 0.0 END) as avg_actual,
    ABS(AVG(model_prob) - AVG(CASE WHEN bet_status = 'won' THEN 1.0 ELSE 0.0 END)) as calibration_error
FROM bet_log
WHERE created_at >= NOW() - INTERVAL '7 days'
  AND bet_status IN ('won', 'lost')
  AND is_paper_money = FALSE;

-- Paper trading performance
SELECT
    COUNT(*) as num_bets,
    AVG(model_prob) as avg_prob,
    AVG(CASE WHEN bet_status = 'won' THEN 1.0 ELSE 0.0 END) as win_rate
FROM bet_log
WHERE is_paper_money = TRUE
  AND bet_status IN ('won', 'lost');
```

---

## ✅ Completion Status

### Phase 1 (Deployed - Active) ✅
- [x] ELO-only baseline model trained
- [x] Platt scaling calibration applied (param_id=3)
- [x] Test set performance validated (54.98% accuracy, 4.03% calibration)
- [x] Results documented
- [x] Deployment guide written
- [x] Paper trading system deployed (V39-V40)
- [x] Project containerized (Docker complete)
- [x] Active for 2025-26 season

### Phase 2 (Investigation Complete - Not Deployed) ✅
- [x] Sessions 1-6 completed (all 6 sessions in 2 hours)
- [x] Rest days feature (99.4% coverage) - **Found useless**
- [x] Goalie GAA feature (95.4% coverage) - **Found weak**
- [x] Enhanced model trained (55.19% accuracy)
- [x] Platt scaling retrained (param_id=7, not active)
- [x] Comprehensive investigation conducted
- [x] Performance comparison documented
- [x] Root cause analysis completed
- [x] Final recommendations written
- [x] **Decision: Do NOT deploy Phase 2**

---

## 🎯 Recommendations for 2026-27 Season

### Deploy Phase 1 ✅

**Model Configuration:**
- ELO differential only
- Platt scaling: a=0.1977, b=0.0353 (param_id=3)
- Edge threshold: 4-6% (conservative)
- Kelly multiplier: 0.25x or lower

**Betting Strategy:**
- Prioritize calibration quality over bet frequency
- Wait for high-edge opportunities
- Use paper trading in parallel
- Monitor calibration weekly
- Pause if error >7%

### Do NOT Deploy Phase 2 ❌

**Reasons:**
- Calibration 127% worse (9.13% vs 4.03%)
- Marginal accuracy gain (+0.21%)
- Sample size reduced 28%
- Added complexity without value
- Failed all success criteria

### Future Work (Low Priority)

**Only if willing to invest significant effort:**
- Try game-level goalie stats (not season average)
- Explore alternative bet types (totals, props)
- Consider live betting infrastructure
- Accept limitations and focus on execution

**More likely path:**
- Stick with Phase 1 long-term
- Optimize bet selection strategy
- Focus on bankroll management
- Accept that NHL markets are efficient

---

## 📞 Support & Common Commands

### Common Workflows

```bash
# Train Phase 1 baseline model
python -m pipelines.analysis.train_baseline_model

# Generate predictions for today's games
python -m pipelines.pricing.compute_game_pricing_elos
python -m pipelines.pricing.compute_edges

# Select bets (real + paper)
python -m pipelines.betting.select_bets
python -m pipelines.betting.select_paper_bets

# Preview edges before betting
python -m pipelines.betting.preview_edges

# View reports
python -m pipelines.betting.reports
```

### If Things Break

1. **Check logs**: `logs/` directory
2. **Verify database**: Run simple query
3. **Check pipelines**: Run diagnostic scripts
4. **Review changes**: `git log --oneline -10`

---

**Created:** April 9, 2026
**Phase 1 Deployed:** April 24, 2026
**Phase 2 Investigation Complete:** June 25, 2026
**Last Updated:** June 25, 2026
**Current Status:** 🟢 Ready for 2026-27 Season - Phase 1 Recommended
**Next Milestone:** September 2026 - Preseason validation
**Season Target:** 2026-27 NHL Season (October 2026)
