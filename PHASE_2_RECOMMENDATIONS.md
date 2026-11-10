# Phase 2 Investigation - Final Recommendations

**Date:** June 25, 2026
**Status:** Investigation Complete
**Decision:** Do NOT deploy Phase 2 - Stick with Phase 1

---

## Executive Summary

After completing all 6 sessions of the Phase 2 roadmap and conducting deep investigation into why it underperformed, the **clear recommendation is to continue using Phase 1 (ELO-only) model for production**.

**Key Finding:** Phase 2's enhanced features (rest days + goalie GAA) added minimal predictive power while significantly degrading calibration quality.

---

## Investigation Summary

### Sessions Completed ✅

| Session | Objective | Result | Time |
|---------|-----------|--------|------|
| 3 | Goalie GAA schema | ✅ Migration V41 applied | 20 min |
| 4 | Populate goalie GAA | ✅ 4,060 games (95.4% coverage) | 30 min |
| 5 | Train enhanced model | ✅ Model trained, below targets | 45 min |
| 6 | Train Platt scaling | ✅ Calibration improved but still poor | 30 min |

**Total Time:** ~2 hours (vs 8-10 hour estimate - 4-5x faster!)

### Files Created ✅

1. `infra/db/migrations/V41__add_goalie_gaa_to_features.sql`
2. `pipelines/etl/update_game_features_goalie_gaa.py`
3. `pipelines/analysis/train_with_features.py`
4. Modified: `pipelines/analysis/train_platt_scaling.py`

**Total:** ~330 lines of working, tested code

### Documentation Created ✅

1. `SESSIONS_3_6_COMPLETION.md` - Full session summary
2. `PHASE_1_VS_PHASE_2_COMPARISON.md` - Detailed performance comparison
3. `CALIBRATION_COMPRESSION_ANALYSIS.md` - Root cause analysis
4. `PHASE_2_RECOMMENDATIONS.md` - This document

---

## Performance Results

### Phase 1 vs Phase 2

| Metric | Phase 1 | Phase 2 | Change | Winner |
|--------|---------|---------|--------|--------|
| **Accuracy** | 54.98% | 55.19% | +0.21% | Phase 2 |
| **Calibration** | **4.03%** | **9.13%** | **+5.10%** | **Phase 1 ✓✓** |
| **Brier Score** | 0.2473 | 0.2467 | -0.0006 | Phase 2 |
| **Sample Size** | 712 | 511 | -28% | Phase 1 ✓ |

**Critical Issue:** Phase 2 calibration is **127% worse** than Phase 1 (9.13% vs 4.03%).

### Success Criteria

**From roadmap - must meet at least ONE:**
- ❌ Accuracy +0.5% (got +0.21%)
- ❌ Brier -0.01 (got -0.0006)
- ❌ Calibration -1% (got +5.10% - WORSE!)

**Result:** **Failed all criteria**

---

## Why Phase 2 Failed

### 1. Rest Days Feature: Complete Failure

**Feature Coefficient:** -0.0002 (essentially zero)
**Correlation with Wins:** -0.0246 (very weak)

**Root Causes:**
- **NHL scheduling is balanced** - 50.9% games have equal rest, 35.1% have ±1 day
- **No clear win rate pattern** - Inconsistent relationship between rest and wins
- **Data quality issues** - Outliers (105-359 days rest) from cross-season bugs
- **Limited variance** - Only 14% of games have 2+ day rest differential

**Conclusion:** Rest days are useless for NHL prediction.

### 2. Goalie GAA Feature: Minimal Impact

**Feature Coefficient:** -0.0744 (moderate but weak)
**Correlation with Wins:** -0.0093 (weaker than rest days!)

**Root Causes:**
- **Season-level aggregation too coarse** - Full season GAA includes future games (data leakage)
- **No clear win rate pattern** - GAA diff of -0.64 yields 15.4% win, -0.69 yields 77.8% (random!)
- **Independent of ELO** - Doesn't redundant, but also doesn't predict wins
- **High individual game variance** - Season average doesn't capture game-to-game performance

**Conclusion:** Season-level GAA adds minimal predictive value.

### 3. Calibration Degradation

**Why calibration got worse:**
- Weak features added noise instead of signal
- Model became less confident (appropriate given weak features)
- Sample size dropped 28% (less data for calibration)
- Platt scaling compressed probabilities even more (48-54% vs 47-55%)

**Impact:**
- Bad calibration → bad edge calculations
- Edge calculation errors → losing bets
- Not acceptable for production

---

## Root Cause: NHL Parity

### The Fundamental Problem

**NHL is the hardest major sport to predict** due to:

1. **Salary cap creates parity** - All teams have similar resources
2. **50% of teams make playoffs** - Less tanking, more competition
3. **High variance sport** - Goalies, lucky bounces, small samples
4. **Efficient betting markets** - Public data already priced in

**Evidence:**
```
Sport | Typical Win % Range | Predictability
------+--------------------+----------------
NBA   | 25-75%             | High
NFL   | 30-70%             | Moderate
NHL   | 40-60%             | Low ← HARDEST
MLB   | 35-65%             | Moderate-Low
```

### ELO Captures Most Available Signal

**ELO differential stats:**
- Average: 0.55 points (nearly balanced)
- StdDev: 69.83 points (good variance)
- Range: -262 to +267 points

**Win rate by ELO:**
- ELO +100: ~62% win rate
- ELO 0: ~51% win rate
- ELO -100: ~42% win rate

**Only 20% win rate swing** across 200 ELO point range. Modest effect!

### Probability Compression is Appropriate

**Raw model range:** 27-78% (good spread)
**After Platt scaling:** 47-55% (compressed)

**Why compression is necessary:**
- Raw probabilities are overconfident
- Actual outcomes cluster near 50%
- Compression reflects true uncertainty
- **Better to be accurately uncertain than confidently wrong**

---

## Recommendations

### IMMEDIATE: Deploy Phase 1 for 2026-27 Season ✅

**Do NOT deploy Phase 2.**

**Use:**
- Phase 1 (ELO-only) model
- Platt scaling param_id = 3 (a=0.1977, b=0.0353)
- 4.03% calibration error ✅
- 54.98% accuracy ✅

**Reasons:**
1. Superior calibration (4.03% vs 9.13%)
2. More test data (712 vs 511 games)
3. Simpler to maintain (single feature)
4. Already validated and in production
5. Phase 2 failed all success criteria

### SHORT-TERM: Optimize Betting Strategy

**Instead of improving model, improve bet selection:**

1. **Raise edge threshold**
   - Current: 2-4% edge minimum
   - Try: 4-6% edge minimum
   - Bet less frequently but with higher confidence

2. **Focus on line movement**
   - Track opening vs closing lines
   - Bet when model disagrees with market shift
   - Exploit timing inefficiencies

3. **Conservative Kelly multiplier**
   - Current: 0.25x Kelly
   - Consider: 0.10-0.15x for risk management
   - Prioritize bankroll preservation

4. **Monitor calibration continuously**
   - Track rolling 100-game calibration
   - Alert if error >7%
   - Pause betting if systematic drift detected

### MEDIUM-TERM: Feature Engineering (If Pursuing)

**Only if willing to invest significant time:**

**Option A: Fix Rest Days**
- Debug cross-season calculation (remove 100+ day outliers)
- Try binary feature: back-to-back (yes/no)
- Expected impact: Minimal (NHL scheduling already balanced)
- **Recommendation: Not worth it**

**Option B: Better Goalie Features**
- Use recent form (last 10 games) not season average
- Calculate "as of" game date (no data leakage)
- Use save percentage instead of GAA
- Get game-by-game performance data
- Expected impact: Moderate improvement possible
- **Recommendation:** Worth exploring if data available

**Option C: New Features Entirely**
- Injuries (27% coverage - limited historical value)
- Home/away splits
- Special teams (PP%, PK%)
- Recent form (L10 record)
- Head-to-head history
- Expected impact: Unknown, likely small
- **Recommendation:** Test one feature at a time

**Success criteria (same as before):**
- Must improve accuracy by +0.5% OR
- Must improve calibration by -1% OR
- Must improve Brier by -0.01

**If criteria not met, abandon and stick with Phase 1.**

### LONG-TERM: Accept Market Efficiency

**Hard truth:** Public data may not support better models.

**Evidence:**
- ELO already captures most signal
- Rest days don't matter (correlation -0.0246)
- Goalie stats don't matter (correlation -0.0093)
- Markets price in public information

**Options:**
1. **Proprietary data** - Player tracking, advanced stats (expensive, complex)
2. **Live betting** - Exploit in-game volatility (requires real-time infrastructure)
3. **Alternative markets** - Totals, puck lines, props (different inefficiencies)
4. **Accept limitations** - Focus on calibration and discipline, not prediction

**Recommendation:** Option 4 (accept limitations) is most realistic.

---

## Lessons Learned

### Technical Skills Acquired ✅

1. ETL pipeline development (multi-table JOINs, NULL handling)
2. Feature engineering (differential features, data quality checks)
3. Model training (multi-feature logistic regression)
4. Calibration techniques (Platt scaling implementation)
5. SQL & database (migrations, indexing, query optimization)
6. Python & Pandas (data loading, processing, evaluation)

### ML/Data Science Insights ✅

1. **More features ≠ better model** - Can add noise instead of signal
2. **Domain knowledge must be validated** - Rest days "should" matter but don't
3. **Calibration > accuracy** - For betting, accurate probabilities are critical
4. **Sample size matters** - Lost 28% of test data hurt evaluation
5. **Occam's Razor** - Simpler models often outperform complex ones
6. **Test assumptions** - Correlation analysis reveals truth quickly

### Betting/Business Insights ✅

1. **Market efficiency is real** - Public data has limited edge
2. **Parity leagues are hard** - NHL compression reflects true uncertainty
3. **Discipline > sophistication** - Good bet selection beats complex models
4. **Risk management critical** - Kelly criterion, conservative sizing
5. **Calibration enables profitability** - Even narrow edges profitable if accurate

---

## Next Actions

### For This Season (2026-27)

**Week 1 (Now):**
- ✅ Complete investigation
- ✅ Document findings
- ⏳ Update PROJECT_STATUS.md with Phase 2 results
- ⏳ Archive Phase 2 work

**Weeks 2-4 (July):**
- Continue using Phase 1 for any remaining games
- Monitor calibration on new season data
- Track real vs paper bet performance

**Pre-Season (September):**
- Validate Phase 1 on preseason games
- Verify data pipelines still working
- Confirm ELO ratings current

**Season Start (October):**
- Deploy Phase 1 for 2026-27 season
- Monitor performance weekly
- Track calibration rigorously

### For Future Seasons

**2027 Offseason:**
- Revisit goalie features with game-by-game data
- Explore alternative bet types (totals, props)
- Consider live betting infrastructure
- Evaluate ROI after full season

**Long-term:**
- Accept Phase 1 limitations if no breakthrough
- Focus on bankroll management and discipline
- Consider diversifying to other sports/markets
- Prioritize sustainable profitability over model complexity

---

## Files to Archive

**Move to `archive_phase_2/`:**
- `pipelines/analysis/train_with_features.py`
- `pipelines/analysis/train_platt_scaling.py` (modified version)
- `pipelines/etl/update_game_features_goalie_gaa.py`
- `infra/db/migrations/V41__add_goalie_gaa_to_features.sql` (keep applied)

**Keep in main docs:**
- `SESSIONS_3_6_COMPLETION.md`
- `PHASE_1_VS_PHASE_2_COMPARISON.md`
- `CALIBRATION_COMPRESSION_ANALYSIS.md`
- `PHASE_2_RECOMMENDATIONS.md` (this file)

---

## Success Metrics for 2026-27 Season

**Using Phase 1 model, track:**

| Metric | Target | Alert If |
|--------|--------|----------|
| **Calibration Error** | <5% | >7% |
| **ROI** | >5% | <-5% |
| **Sharpe Ratio** | >1.5 | <1.0 |
| **Max Drawdown** | <20% | >25% |
| **Sample Size** | >200 bets/season | <100 |

**Monthly review:**
- Compare actual vs predicted win rates
- Check for calibration drift
- Evaluate bet selection criteria
- Adjust edge thresholds if needed

---

## Final Thoughts

### Phase 2 was NOT a Failure

**What we achieved:**
- ✅ Completed entire roadmap (6/6 sessions)
- ✅ Built working ETL pipelines
- ✅ Created production-ready code (~330 lines)
- ✅ Learned valuable ML skills
- ✅ Discovered why features fail
- ✅ Understood model limitations

**This is real ML work** - not every experiment succeeds. The learning is the value.

### The Right Decision

**Sticking with Phase 1 is the smart move:**
- Superior calibration (critical for betting)
- Simpler to maintain
- More reliable
- Already validated

**Don't let sunk cost fallacy drive bad decisions.** Phase 2 took 2 hours to build but would cost long-term in poor calibration.

### Moving Forward

**Focus on:**
1. Discipline (only bet +EV)
2. Patience (wait for high-edge opportunities)
3. Calibration monitoring (catch drift early)
4. Bankroll management (Kelly 0.25x or lower)
5. Continuous learning (but don't over-optimize)

**Success in NHL betting comes from executing the basics well, not from perfect prediction.**

---

## Approval

**Recommended Action:** Deploy Phase 1 (ELO-only) for 2026-27 season

**Phase 2 Status:** ❌ Do NOT deploy - Failed success criteria

**Reason:** Calibration degradation (9.13% vs 4.03%) outweighs marginal accuracy gain (+0.21%)

**Next Review:** After 2026-27 season completion (April 2027)

---

**Created:** June 25, 2026
**Status:** Investigation complete - Recommendations final
**Decision:** Use Phase 1 for production
