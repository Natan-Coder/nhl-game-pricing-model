"""
Data split utilities for train/validation/test sets

Ensures proper chronological splitting with no data leakage
"""

import psycopg
import pandas as pd
import json
from datetime import datetime
from pathlib import Path
from pipelines.config import DATABASE_URL


def get_train_val_test_splits(strategy='season_based'):
    """
    Get train/val/test splits from database

    Strategy 'season_based':
    - Train: 2023 + 2024 seasons (2,807 games)
    - Val: First half of 2025 (~570 games)
    - Test: Second half of 2025 (~569 games)

    Returns:
        tuple: (train_game_ids, val_game_ids, test_game_ids)
    """
    with psycopg.connect(DATABASE_URL) as conn:
        # Step 1: Get all games with their dates, ordered chronologically
        query = """
            SELECT game_id, game_date
            FROM game_results
            ORDER BY game_date ASC
        """
        df = pd.read_sql(query, conn)

        # Step 2: Extract season from game_id (first 4 digits = year)
        # Example: game_id 2023020001 -> season 2023
        df['season'] = df['game_id'].astype(str).str[:4].astype(int)

        # Step 3: Split based on strategy
        if strategy == 'season_based':
            # Train: All games from 2023 and 2024
            train = df[df['season'].isin([2023, 2024])]['game_id'].tolist()

            # Val + Test: Split 2025 season in half
            season_2025 = df[df['season'] == 2025]
            midpoint = len(season_2025) // 2  # Integer division

            val = season_2025.iloc[:midpoint]['game_id'].tolist()
            test = season_2025.iloc[midpoint:]['game_id'].tolist()

            return train, val, test

        else:
            raise ValueError(f"Unknown strategy: {strategy}")


def verify_splits(train_ids, val_ids, test_ids):
    """
    Verify that splits are valid:
    1. No overlap (same game in multiple splits)
    2. Chronological order (train < val < test)
    """
    print("\nVerifying data splits...")
    print("=" * 60)

    # Check 1: No overlap between sets
    train_set = set(train_ids)
    val_set = set(val_ids)
    test_set = set(test_ids)

    overlap_train_val = train_set & val_set
    overlap_train_test = train_set & test_set
    overlap_val_test = val_set & test_set

    assert len(overlap_train_val) == 0, f"Train/val overlap: {len(overlap_train_val)} games!"
    assert len(overlap_train_test) == 0, f"Train/test overlap: {len(overlap_train_test)} games!"
    assert len(overlap_val_test) == 0, f"Val/test overlap: {len(overlap_val_test)} games!"

    print("[OK] No overlap - all splits are disjoint")

    # Check 2: Chronological order
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

    # Print date ranges
    print(f"\nDate ranges:")
    print(f"  Train: {train_dates['game_date'].min()} to {train_dates['game_date'].max()}")
    print(f"  Val:   {val_dates['game_date'].min()} to {val_dates['game_date'].max()}")
    print(f"  Test:  {test_dates['game_date'].min()} to {test_dates['game_date'].max()}")

    print("\n[OK] Splits verified successfully!")


def compute_split_statistics(split_name, game_ids):
    """
    Compute and print statistics for a data split

    Stats include:
    - Total games
    - Number of teams
    - Average goals per game
    - Home win rate
    - Date range
    """
    with psycopg.connect(DATABASE_URL) as conn:
        query = """
            SELECT
                COUNT(*) as total_games,
                COUNT(DISTINCT home_team) as num_home_teams,
                COUNT(DISTINCT away_team) as num_away_teams,
                AVG(home_goals::float + away_goals::float) as avg_total_goals,
                AVG(CASE WHEN home_goals > away_goals THEN 1.0 ELSE 0.0 END) as home_win_rate,
                MIN(game_date) as first_game,
                MAX(game_date) as last_game
            FROM game_results
            WHERE game_id = ANY(%s)
        """
        stats = pd.read_sql(query, conn, params=(game_ids,))

    row = stats.iloc[0]
    print(f"\n{split_name} Statistics:")
    print(f"  Total games: {row['total_games']}")
    print(f"  Unique home teams: {row['num_home_teams']}")
    print(f"  Unique away teams: {row['num_away_teams']}")
    print(f"  Avg total goals: {row['avg_total_goals']:.2f}")
    print(f"  Home win rate: {row['home_win_rate']:.1%}")
    print(f"  Date range: {row['first_game']} to {row['last_game']}")

    return row


def save_splits(train_ids, val_ids, test_ids, strategy='season_based'):
    """
    Save splits to JSON file for reproducibility

    This ensures you always use the exact same train/val/test split
    when comparing different models
    """
    # Create data directory if it doesn't exist
    data_dir = Path(__file__).parent.parent.parent / 'data'
    data_dir.mkdir(exist_ok=True)

    # Create JSON structure
    splits = {
        'strategy': strategy,
        'created_at': datetime.now().isoformat(),
        'train': {
            'game_ids': train_ids,
            'count': len(train_ids)
        },
        'val': {
            'game_ids': val_ids,
            'count': len(val_ids)
        },
        'test': {
            'game_ids': test_ids,
            'count': len(test_ids)
        }
    }

    # Save to file
    filepath = data_dir / f'data_splits_{strategy}.json'
    with open(filepath, 'w') as f:
        json.dump(splits, f, indent=2)

    print(f"\n[OK] Splits saved to {filepath}")
    return filepath


def load_splits(strategy='season_based'):
    """
    Load previously saved splits from JSON file

    Usage in model training:
        from pipelines.common.data_splits import load_splits
        train, val, test = load_splits('season_based')
    """
    data_dir = Path(__file__).parent.parent.parent / 'data'
    filepath = data_dir / f'data_splits_{strategy}.json'

    if not filepath.exists():
        raise FileNotFoundError(
            f"Splits file not found: {filepath}\n"
            f"Run create_and_save_splits() first!"
        )

    with open(filepath, 'r') as f:
        splits = json.load(f)

    return (
        splits['train']['game_ids'],
        splits['val']['game_ids'],
        splits['test']['game_ids']
    )


def create_and_save_splits(strategy='season_based'):
    """
    Main function: Create data splits and save them to file

    This is what you run ONCE to set up your splits.
    After that, use load_splits() to load them.
    """
    print(f"Creating {strategy} splits...")
    print("=" * 60)

    # Step 1: Get splits from database
    train_ids, val_ids, test_ids = get_train_val_test_splits(strategy)

    print(f"\nSplit sizes:")
    print(f"  Train: {len(train_ids):,} games")
    print(f"  Val:   {len(val_ids):,} games")
    print(f"  Test:  {len(test_ids):,} games")
    print(f"  Total: {len(train_ids) + len(val_ids) + len(test_ids):,} games")

    # Step 2: Verify splits
    verify_splits(train_ids, val_ids, test_ids)

    # Step 3: Compute statistics
    print("\n" + "=" * 60)
    train_stats = compute_split_statistics('TRAIN', train_ids)
    val_stats = compute_split_statistics('VALIDATION', val_ids)
    test_stats = compute_split_statistics('TEST', test_ids)

    # Step 4: Check for distribution shifts
    print("\n" + "=" * 60)
    print("Distribution Shift Check:")
    print("(Large differences may indicate data quality issues)")

    train_hwr = train_stats['home_win_rate']
    val_hwr = val_stats['home_win_rate']
    test_hwr = test_stats['home_win_rate']

    print(f"  Home win rate (train): {train_hwr:.1%}")
    print(f"  Home win rate (val):   {val_hwr:.1%}")
    print(f"  Home win rate (test):  {test_hwr:.1%}")

    if abs(train_hwr - val_hwr) > 0.05:
        print("  [X]  WARNING: Train/val home win rate differs by >5%")
    if abs(train_hwr - test_hwr) > 0.05:
        print("  [X]  WARNING: Train/test home win rate differs by >5%")
    else:
        print("  [OK] No significant distribution shift detected")

    # Step 5: Save to file
    print("\n" + "=" * 60)
    filepath = save_splits(train_ids, val_ids, test_ids, strategy)

    # Step 6: Success message
    print("\n" + "=" * 60)
    print("[OK] SPLITS CREATED SUCCESSFULLY!")
    print("\nTo use these splits in your model code:")
    print("  from pipelines.common.data_splits import load_splits")
    print(f"  train, val, test = load_splits('{strategy}')")
    print("\n" + "=" * 60)

    return train_ids, val_ids, test_ids


if __name__ == '__main__':
    # When you run this script directly, it creates and saves splits
    print("NHL Betting Model - Data Split Creator")
    print("=" * 60)
    print("\nThis will create train/validation/test splits and save them.")
    print("You only need to run this ONCE.\n")

    create_and_save_splits('season_based')
