# Feature Engineering TODO

**Last Updated:** April 9, 2026
**Status:** Paused - Deploying ELO-only model first

---

## Overview

This document tracks additional features that have database schema ready but need ETL pipelines to calculate and populate data.

**Current Situation:**
- ✅ Database schema exists (migrations applied)
- ❌ Feature values not calculated/populated
- ❌ Cannot train models until data is available

---

## Feature Status Summary

| Feature | Schema | Data Coverage | Priority | Estimated Work |
|---------|--------|---------------|----------|----------------|
| **Rest Days** | ✅ Ready | 9.9% | High | 2-3 hours |
| **Injuries** | ✅ Ready | 26.6% | Medium | 3-4 hours |
| **Goalie Stats** | ✅ Ready | 0% | Low | 4-6 hours |

---

## 1. Rest Days Feature

### Current Status
- **Database columns:** `home_rest_days`, `away_rest_days`, `home_rest`, `away_rest`
- **Coverage:** 9.9% (412 out of 4,149 games)
- **Migration:** `V28__rest_days.sql`

### What's Missing
Need to write ETL script to:
1. For each game, find each team's previous game
2. Calculate days between games
3. Populate `home_rest_days` and `away_rest_days` columns

### Implementation Plan

**Script to create:** `pipelines/etl/calculate_rest_days.py`

**Logic:**
```python
# For each team and game:
# 1. Query: Find previous game for this team
# 2. Calculate: days_between = current_game_date - previous_game_date
# 3. Update: SET home_rest_days = days_between WHERE game_id = current_game
```

**Pseudo-code:**
```sql
-- For home team
UPDATE game_features gf
SET home_rest_days = (
    SELECT gf.game_date - prev_game.game_date
    FROM game_features prev_game
    WHERE (prev_game.home_team = gf.home_team OR prev_game.away_team = gf.home_team)
      AND prev_game.game_date < gf.game_date
    ORDER BY prev_game.game_date DESC
    LIMIT 1
)
```

### Expected Feature Values
- **Range:** 0-7 days (typical)
- **Back-to-back:** 0 or 1 days rest
- **Normal:** 2-3 days rest
- **Long break:** 4+ days rest

### Model Usage
```python
# Feature options:
rest_diff = home_rest_days - away_rest_days  # Differential (recommended)
# OR
X = [elo_diff, home_rest_days, away_rest_days]  # Separate features
```

---

## 2. Injuries Feature

### Current Status
- **Database columns:** `home_recent_injuries`, `away_recent_injuries`, `home_total_injuries`, `away_total_injuries`
- **Coverage:** 26.6% (1,104 out of 4,149 games)
- **Migration:** `V31__player_injuries.sql`, `V32__injury_features.sql`

### What's Missing
Coverage is partial. Need to:
1. Check if `pipelines/etl/update_game_features_injuries.py` exists
2. Run it to backfill historical games
3. Verify coverage improves

### Implementation Plan

**Check existing scripts:**
```bash
ls pipelines/etl/*injur*
```

**If script exists:** Run it to backfill
**If not:** Create `pipelines/etl/calculate_injuries.py`

**Logic:**
```python
# For each game:
# 1. Query player_injuries table for injuries active on game_date
# 2. Count injuries for home team
# 3. Count injuries for away team
# 4. Update game_features
```

### Data Source
- **Table:** `player_injuries`
- **From:** `pipelines/etl/ingest_player_injuries.py`
- **Note:** Only captures injuries from 2025-26 season onwards (current data)

### Model Usage
```python
# Feature options:
injury_diff = home_total_injuries - away_total_injuries  # Differential
# OR
X = [elo_diff, home_recent_injuries, away_recent_injuries]  # Recent only
```

### Limitations
- **Historical data:** Injury data only available for 2025-26 season
- **Pre-2025 games:** Will have NULL or 0 for injury features
- **Impact:** May need to filter training data to only recent seasons

---

## 3. Goalie Stats Feature

### Current Status
- **Database columns:** `home_goalie_sv_pct`, `away_goalie_sv_pct`, `home_goalie_id`, `away_goalie_id`
- **Coverage:** 0% save percentage, 97% goalie IDs
- **Migration:** `V29__goalie_tables.sql`

### What's Missing
Two problems to solve:

#### Problem 1: Save Percentage Not Calculated
`pipelines/etl/calculate_goalie_stats.py` calculates GAA but not save percentage:
```python
# Current (line 96):
%s, NULL, %s, %s, %s,  # save_pct is NULL
```

**Need:** Shots data to calculate save% = saves / shots_against

**Options:**
- **A)** Fetch shots data from NHL API (if available)
- **B)** Use GAA instead of save% as the feature
- **C)** Skip goalie features entirely

#### Problem 2: Save Percentage Not Populated
Even if calculated, need to run:
```bash
python -m pipelines.etl.calculate_goalie_stats  # Calculate stats
python -m pipelines.etl.update_game_features_goalies  # Populate game_features
```

### Implementation Plan (Option A)

**Step 1:** Update `ingest_goalie_stats.py` or `calculate_goalie_stats.py`
- Add shots data fetching
- Calculate save% properly
- Store in `goalie_stats` table

**Step 2:** Run backfill
```bash
python -m pipelines.etl.calculate_goalie_stats  # Recalculate with save%
python -m pipelines.etl.update_game_features_goalies  # Update game_features
```

### Implementation Plan (Option B - Simpler)

Use GAA instead:
```python
# Modify train script to use:
X = [elo_diff, home_goalie_gaa - away_goalie_gaa]
```

**But:** Need to add GAA columns to `game_features` schema first.

### Model Usage (if implemented)
```python
# Feature options:
goalie_diff = home_goalie_sv_pct - away_goalie_sv_pct  # Differential
# OR
X = [elo_diff, home_goalie_sv_pct, away_goalie_sv_pct]  # Separate
```

---

## Priority & Sequencing

### Recommended Order (when resuming):

**1. Rest Days** (Highest Priority)
- **Why:** Simplest to implement, universal data availability
- **Impact:** Medium (back-to-back games are important factor)
- **Effort:** Low (2-3 hours)

**2. Injuries** (Medium Priority)
- **Why:** Partial data exists, moderate effort
- **Impact:** Medium-High (injuries significantly affect outcomes)
- **Effort:** Medium (3-4 hours to backfill)
- **Note:** Limited to recent seasons only

**3. Goalie Stats** (Lower Priority)
- **Why:** Requires data source work, highest effort
- **Impact:** Medium (goalie matchups matter but already captured in ELO somewhat)
- **Effort:** High (4-6 hours, may need new data sources)

---

## Testing Protocol (For Each Feature)

When adding a new feature:

1. **Verify data coverage**
   ```bash
   python -m pipelines.analysis.diagnose_<feature>_coverage
   ```

2. **Create training script**
   ```bash
   cp pipelines/analysis/train_baseline_model.py pipelines/analysis/train_with_<feature>.py
   ```

3. **Modify query to include new features**
   ```python
   X = df[['elo_diff', '<new_feature_diff>']]
   ```

4. **Train and compare to baseline**
   ```bash
   python -m pipelines.analysis.train_with_<feature>
   ```

5. **Evaluate improvement**
   - Accuracy should improve by >0.5%
   - Brier score should decrease
   - Calibration error should decrease

6. **Document results** in `PHASE_<N>_RESULTS.md`

---

## Success Criteria for Adding Features

A feature is worth adding if it meets **any** of these criteria:

| Metric | Improvement Threshold |
|--------|----------------------|
| Accuracy | +0.5% or more |
| Brier Score | -0.01 or more (decrease) |
| Calibration Error | -1% or more (decrease) |

If a feature doesn't meet these thresholds, it adds complexity without value - skip it.

---

## Related Scripts & Files

### Diagnostic Scripts (Created)
- `pipelines/analysis/diagnose_goalie_coverage.py`
- `pipelines/analysis/diagnose_rest_days_coverage.py`

### Existing ETL Scripts (To Use/Modify)
- `pipelines/etl/calculate_goalie_stats.py` - Needs save% calculation
- `pipelines/etl/update_game_features_goalies.py` - Ready to use (if data exists)
- `pipelines/etl/ingest_player_injuries.py` - Active injury ingestion
- `pipelines/etl/update_game_features_injuries.py` - Check if exists

### Training Script Templates
- `pipelines/analysis/train_baseline_model.py` - ELO-only baseline
- `pipelines/analysis/train_with_goalies.py` - Template (needs data)

---

## Next Session Checklist

When resuming feature engineering work:

- [ ] Review `PHASE_1_RESULTS.md` for baseline performance
- [ ] Pick highest priority feature (rest days recommended)
- [ ] Write/run ETL script to populate data
- [ ] Verify coverage with diagnostic script
- [ ] Create `train_with_<feature>.py` script
- [ ] Train model and compare to baseline
- [ ] Document results
- [ ] Repeat for next feature if improvement is significant

---

**Last Updated:** April 9, 2026
**Next Review:** When resuming feature engineering after Phase 1 deployment
