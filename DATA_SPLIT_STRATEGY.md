# NHL Betting Model - Data Split Strategy

**Date:** March 22, 2026
**Purpose:** Define how to split data for training, validation, and testing

---

## Available Data Summary

From database audit:
- **2023 season:** 1,404 games
- **2024 season:** 1,403 games
- **2025 season:** 1,139 games
- **Total:** 3,946 games

---

## Split Strategy Options

### Option A: Season-Based Split (RECOMMENDED)

**Train:** 2023 + 2024 seasons (2,807 games = 71%)
**Validation:** First half of 2025 season (~570 games = 14%)
**Test:** Second half of 2025 season (~569 games = 14%)

**Pros:**
- Clean temporal split (no data leakage)
- Large training set (2,807 games)
- Validation and test both from same season (consistent conditions)
- Test set represents most recent data (best proxy for future performance)

**Cons:**
- 2025 season may differ from 2023-2024 (rule changes, new players)
- Smaller validation/test sets than ideal

**Use Case:** Best for final model validation

---

### Option B: Rolling Window Split

**Train:** 2023 + first 2/3 of 2024 (~2,340 games = 59%)
**Validation:** Last 1/3 of 2024 (~468 games = 12%)
**Test:** 2025 season (1,139 games = 29%)

**Pros:**
- Larger test set (1,139 games = better statistical power)
- Simulates real deployment (train on past, test on future)
- Validation set from different season than test (less correlated)

**Cons:**
- Smaller training set
- 2025 may be too different from 2023-2024

**Use Case:** Good for testing temporal generalization

---

### Option C: Walk-Forward Validation

**Multiple Splits:**
1. Train: 2023 → Validate: First half 2024 → Test: Second half 2024
2. Train: 2023 + 2024 → Validate: First half 2025 → Test: Second half 2025

**Pros:**
- Tests model on multiple time periods
- More robust estimate of generalization
- Detects if model degrades over time

**Cons:**
- More complex to implement
- Requires multiple training runs

**Use Case:** Best for rigorous validation before going live

---

## RECOMMENDED APPROACH

Use **Option A** for development, then **Option C** for final validation:

### Phase 1: Model Development (Use Option A)
- Iterate quickly with single train/val/test split
- Tune hyperparameters on validation set
- Report final metrics on test set

### Phase 2: Final Validation (Use Option C)
- Once model is finalized, run walk-forward validation
- Ensure model works across multiple time periods
- This is the "final exam" before paper trading

---

## Implementation

### Data Split Code

```python
import psycopg
from pipelines.config import DATABASE_URL
import pandas as pd

def get_train_val_test_splits(strategy='season_based'):
    """
    Get train/val/test splits from database

    Args:
        strategy: 'season_based', 'rolling_window', or 'walk_forward'

    Returns:
        train_games, val_games, test_games (lists of game_ids)
    """
    with psycopg.connect(DATABASE_URL) as conn:
        # Get all game IDs with dates, ordered chronologically
        query = """
            SELECT game_id, game_date
            FROM game_results
            ORDER BY game_date ASC
        """
        df = pd.read_sql(query, conn)

        # Extract season from game_id (first 4 digits)
        df['season'] = df['game_id'].astype(str).str[:4].astype(int)

        if strategy == 'season_based':
            # Train: 2023 + 2024
            train = df[df['season'].isin([2023, 2024])]['game_id'].tolist()

            # Val: First half of 2025
            season_2025 = df[df['season'] == 2025]
            midpoint = len(season_2025) // 2
            val = season_2025.iloc[:midpoint]['game_id'].tolist()
            test = season_2025.iloc[midpoint:]['game_id'].tolist()

            return train, val, test

        elif strategy == 'rolling_window':
            # Train: 2023 + first 2/3 of 2024
            train_2023 = df[df['season'] == 2023]['game_id'].tolist()
            season_2024 = df[df['season'] == 2024]
            split_point = int(len(season_2024) * 2/3)
            train_2024 = season_2024.iloc[:split_point]['game_id'].tolist()
            train = train_2023 + train_2024

            # Val: Last 1/3 of 2024
            val = season_2024.iloc[split_point:]['game_id'].tolist()

            # Test: 2025
            test = df[df['season'] == 2025]['game_id'].tolist()

            return train, val, test

        elif strategy == 'walk_forward':
            # Return multiple splits for walk-forward validation
            splits = []

            # Split 1: Train on 2023, test on 2024
            season_2024 = df[df['season'] == 2024]
            midpoint_2024 = len(season_2024) // 2
            splits.append({
                'train': df[df['season'] == 2023]['game_id'].tolist(),
                'val': season_2024.iloc[:midpoint_2024]['game_id'].tolist(),
                'test': season_2024.iloc[midpoint_2024:]['game_id'].tolist()
            })

            # Split 2: Train on 2023+2024, test on 2025
            season_2025 = df[df['season'] == 2025]
            midpoint_2025 = len(season_2025) // 2
            splits.append({
                'train': df[df['season'].isin([2023, 2024])]['game_id'].tolist(),
                'val': season_2025.iloc[:midpoint_2025]['game_id'].tolist(),
                'test': season_2025.iloc[midpoint_2025:]['game_id'].tolist()
            })

            return splits

        else:
            raise ValueError(f"Unknown strategy: {strategy}")

# Usage example:
train_ids, val_ids, test_ids = get_train_val_test_splits('season_based')

print(f"Train set: {len(train_ids)} games")
print(f"Validation set: {len(val_ids)} games")
print(f"Test set: {len(test_ids)} games")
```

### Verify Split Quality

```python
def verify_splits(train_ids, val_ids, test_ids):
    """Verify that splits are non-overlapping and chronological"""

    # Check no overlap
    assert len(set(train_ids) & set(val_ids)) == 0, "Train/val overlap!"
    assert len(set(train_ids) & set(test_ids)) == 0, "Train/test overlap!"
    assert len(set(val_ids) & set(test_ids)) == 0, "Val/test overlap!"

    # Check chronological order (using game dates)
    with psycopg.connect(DATABASE_URL) as conn:
        query = """
            SELECT game_id, game_date
            FROM game_results
            WHERE game_id = ANY(%s)
            ORDER BY game_date
        """
        train_dates = pd.read_sql(query, conn, params=(train_ids,))
        val_dates = pd.read_sql(query, conn, params=(val_ids,))
        test_dates = pd.read_sql(query, conn, params=(test_ids,))

    # Latest train date should be before earliest val date
    max_train_date = train_dates['game_date'].max()
    min_val_date = val_dates['game_date'].min()
    min_test_date = test_dates['game_date'].min()

    print(f"Train: {train_dates['game_date'].min()} to {max_train_date}")
    print(f"Val: {min_val_date} to {val_dates['game_date'].max()}")
    print(f"Test: {min_test_date} to {test_dates['game_date'].max()}")

    # Warn if there's overlap in dates (games on same day in different splits)
    if max_train_date >= min_val_date:
        print("⚠️  WARNING: Train and val sets have overlapping dates!")

    print("✅ Splits verified!")
```

---

## Critical Rules for Data Splits

### 1. NO DATA LEAKAGE

**NEVER use test data for:**
- Feature engineering
- Feature selection
- Hyperparameter tuning
- Model architecture decisions
- Calibration fitting

**Test data is ONLY used for:**
- Final model evaluation
- Reporting metrics in papers/reports

### 2. CHRONOLOGICAL ORDERING

Always split data chronologically (not randomly):
- Training data must come BEFORE validation data
- Validation data must come BEFORE test data

**Why?** Random splits leak information from the future (data leakage). In production, we only have past data to predict future games.

### 3. VALIDATION SET USAGE

Use validation set for:
- Hyperparameter tuning (learning rate, regularization, etc.)
- Feature selection (which features to include)
- Early stopping (when to stop training)
- Calibration method selection (Platt vs isotonic)

### 4. TEST SET SANCTITY

**Test set must remain UNTOUCHED until final evaluation:**
1. Develop model using only train + val sets
2. Finalize ALL decisions (features, hyperparameters, etc.)
3. Run model on test set ONCE
4. Report results (no changes allowed after seeing test results)

**If you "peek" at test set during development, you will overfit to it!**

---

## Feature Engineering Rules

### Time-Based Features (CAREFUL!)

**ALLOWED:**
- Rolling averages computed using ONLY past games
- ELO ratings updated chronologically
- "Games in last 7 days" (uses only past data)

**NOT ALLOWED:**
- Team's final season stats
- "Average goals scored this season" (includes future games)
- Any feature computed using data after the prediction date

### Example: Correct Rolling Average

```python
# CORRECT: Only use games before current game
def compute_rolling_avg(team_id, game_date, window_days=30):
    query = """
        SELECT AVG(goals_scored)
        FROM game_results
        WHERE team_id = %s
          AND game_date < %s  -- BEFORE current game
          AND game_date >= %s  -- Within window
    """
    cutoff_date = game_date - timedelta(days=window_days)
    return execute_query(query, (team_id, game_date, cutoff_date))

# WRONG: Uses all games in season (includes future)
def compute_season_avg(team_id, season):
    query = """
        SELECT AVG(goals_scored)
        FROM game_results
        WHERE team_id = %s AND season = %s
    """
    return execute_query(query, (team_id, season))
```

---

## Validation Metrics

Track these metrics on each split:

### Model Performance
- Accuracy (% of correct predictions)
- Calibration error (mean absolute error of probabilities)
- Brier score (probabilistic prediction quality)
- Log loss (penalizes confident wrong predictions)

### Betting Performance
- ROI (return on investment)
- Sharpe ratio (risk-adjusted return)
- Max drawdown (largest losing streak)
- Win rate (% of bets won)

### Consistency Checks
- Train vs val performance gap (should be < 2%)
- Val vs test performance gap (should be < 2%)
- If gaps are large → overfitting or distribution shift

---

## Dataset Statistics

After creating splits, compute and save these stats:

```python
def compute_split_statistics(split_name, game_ids):
    """Compute statistics for a data split"""

    with psycopg.connect(DATABASE_URL) as conn:
        query = """
            SELECT
                COUNT(*) as total_games,
                COUNT(DISTINCT home_team) as num_teams,
                AVG(home_score + away_score) as avg_total_goals,
                AVG(CASE WHEN home_score > away_score THEN 1 ELSE 0 END) as home_win_rate,
                MIN(game_date) as first_game,
                MAX(game_date) as last_game
            FROM game_results
            WHERE game_id = ANY(%s)
        """
        stats = pd.read_sql(query, conn, params=(game_ids,))

    print(f"\n{split_name} Statistics:")
    print(f"  Total games: {stats['total_games'].iloc[0]}")
    print(f"  Teams: {stats['num_teams'].iloc[0]}")
    print(f"  Avg total goals: {stats['avg_total_goals'].iloc[0]:.2f}")
    print(f"  Home win rate: {stats['home_win_rate'].iloc[0]:.1%}")
    print(f"  Date range: {stats['first_game'].iloc[0]} to {stats['last_game'].iloc[0]}")
```

**Check for distribution shifts:**
- If home win rate changes by >5% between splits → investigate
- If avg goals changes by >10% → investigate
- These could indicate rule changes, different eras, etc.

---

## Save Splits to Files

```python
import json

def save_splits(train_ids, val_ids, test_ids, strategy='season_based'):
    """Save splits to JSON files for reproducibility"""

    splits = {
        'strategy': strategy,
        'created_at': datetime.now().isoformat(),
        'train': {'game_ids': train_ids, 'count': len(train_ids)},
        'val': {'game_ids': val_ids, 'count': len(val_ids)},
        'test': {'game_ids': test_ids, 'count': len(test_ids)}
    }

    with open(f'data_splits_{strategy}.json', 'w') as f:
        json.dump(splits, f, indent=2)

    print(f"✅ Splits saved to data_splits_{strategy}.json")

def load_splits(strategy='season_based'):
    """Load previously saved splits"""

    with open(f'data_splits_{strategy}.json', 'r') as f:
        splits = json.load(f)

    return (
        splits['train']['game_ids'],
        splits['val']['game_ids'],
        splits['test']['game_ids']
    )
```

**Why save splits?**
- Reproducibility (always use same train/val/test)
- Compare different models on EXACT same data
- Document what data was used for results

---

## Next Steps

1. **Run split creation script:**
   ```bash
   python -c "from data_split_strategy import *; create_and_save_splits()"
   ```

2. **Verify splits:**
   ```bash
   python -c "from data_split_strategy import *; verify_all_splits()"
   ```

3. **Compute statistics:**
   ```bash
   python -c "from data_split_strategy import *; print_split_statistics()"
   ```

4. **Save to file for later use:**
   - Splits will be saved to `data_splits_season_based.json`
   - Check into git for reproducibility

5. **Use in model training:**
   ```python
   from data_split_strategy import load_splits
   train_ids, val_ids, test_ids = load_splits('season_based')
   ```

---

## Checklist Before Starting Model Development

- [ ] Data splits created (train/val/test)
- [ ] Splits verified (no overlap, chronological)
- [ ] Statistics computed for each split
- [ ] Distribution shifts checked (<5% difference)
- [ ] Splits saved to JSON file
- [ ] JSON file committed to git
- [ ] Feature engineering rules understood (no data leakage)
- [ ] Validation protocol understood (only use test set once)

**Once all boxes checked, you're ready to start building models!**

---

**Last Updated:** March 22, 2026
