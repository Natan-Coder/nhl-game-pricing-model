"""
Test Each Adjustment Individually

This script tests each feature adjustment in isolation to determine which ones
add value and which ones add noise.

We'll compare:
1. Baseline (Raw ELO only)
2. Raw ELO + Form only
3. Raw ELO + Rest only
4. Raw ELO + Goalies only
5. Raw ELO + Injuries only

This helps identify which adjustments are worth keeping and which should be removed.
"""

import pandas as pd
import numpy as np
import logging
import psycopg
from decimal import Decimal
from sklearn.metrics import accuracy_score, brier_score_loss

from pipelines.config import DATABASE_URL
from pipelines.common.data_splits import get_train_val_test_splits
from pipelines.common.logging_setup import setup as setup_logging
from pipelines.pricing.utils import (
    get_recent_form,
    apply_form_adjustment,
    get_rest_adjustment,
    calculate_goalie_advantage,
    get_injury_adjustment
)

setup_logging("INFO")
log = logging.getLogger(__name__)

HOME_ADVANTAGE = 50
SCALE = 400


def calculate_raw_elo_probability(home_elo: float, away_elo: float) -> float:
    """Calculate win probability from raw ELO (no adjustments)."""
    elo_diff = (home_elo + HOME_ADVANTAGE - away_elo) / SCALE
    ten_pow = 10 ** elo_diff
    return ten_pow / (1 + ten_pow)


def calculate_calibration_error(y_true: np.ndarray, y_pred_proba: np.ndarray, bins: int = 10) -> float:
    """Calculate mean absolute calibration error."""
    bin_edges = np.linspace(0, 1, bins + 1)
    bin_indices = np.digitize(y_pred_proba, bin_edges[:-1]) - 1

    errors = []
    for i in range(bins):
        mask = bin_indices == i
        if mask.sum() > 0:
            avg_pred = y_pred_proba[mask].mean()
            avg_true = y_true[mask].mean()
            errors.append(abs(avg_pred - avg_true))

    return np.mean(errors) if errors else 0.0


def calculate_metrics(y_true: np.ndarray, y_pred_proba: np.ndarray) -> dict:
    """Calculate performance metrics."""
    y_pred = (y_pred_proba >= 0.5).astype(int)
    accuracy = accuracy_score(y_true, y_pred)
    brier = brier_score_loss(y_true, y_pred_proba)
    calibration_error = calculate_calibration_error(y_true, y_pred_proba)

    return {
        'accuracy': accuracy,
        'brier_score': brier,
        'calibration_error': calibration_error
    }


def load_all_adjustment_data(game_ids: list) -> pd.DataFrame:
    """
    Load all data needed to test each adjustment individually.

    Includes:
    - Base ELO ratings
    - Form data (for recent form calculation)
    - Rest days
    - Goalie save percentages
    - Injury counts
    - Actual outcomes
    """

    query = """
        SELECT
            gf.game_id,
            gf.home_team,
            gf.away_team,
            gf.home_elo,
            gf.away_elo,
            gf.game_date,
            gf.home_rest_days,
            gf.away_rest_days,
            gf.home_goalie_sv_pct,
            gf.away_goalie_sv_pct,
            gf.home_recent_injuries,
            gf.home_total_injuries,
            gf.away_recent_injuries,
            gf.away_total_injuries,
            CASE WHEN gr.home_goals > gr.away_goals THEN 1 ELSE 0 END as actual_home_win
        FROM game_features gf
        INNER JOIN game_results gr ON gr.game_id = gf.game_id
        WHERE gf.game_id = ANY(%s)
          AND gf.home_elo IS NOT NULL
          AND gf.away_elo IS NOT NULL
        ORDER BY gf.game_date
    """

    with psycopg.connect(
        DATABASE_URL,
        sslmode="require",
        prefer_query_mode=None,
        prepare_threshold=None,
        prepared_statement_cache_queries=None,
    ) as conn:
        df = pd.read_sql(query, conn, params=(game_ids,))

    return df


def calculate_predictions_with_adjustments(df: pd.DataFrame, adjustments: list) -> np.ndarray:
    """
    Calculate win probabilities with specified adjustments applied.

    Args:
        df: DataFrame with game data
        adjustments: List of adjustment names to apply
                    Options: 'form', 'rest', 'goalies', 'injuries'

    Returns:
        Array of home team win probabilities
    """
    predictions = []

    with psycopg.connect(DATABASE_URL) as conn:
        for idx, row in df.iterrows():
            # Start with base ELO
            home_elo_adj = Decimal(str(row['home_elo']))
            away_elo_adj = Decimal(str(row['away_elo']))

            # Apply form adjustment if requested
            if 'form' in adjustments:
                home_form = get_recent_form(row['home_team'], row['game_date'], lookback_games=10, conn=conn)
                away_form = get_recent_form(row['away_team'], row['game_date'], lookback_games=10, conn=conn)
                home_elo_adj = apply_form_adjustment(home_elo_adj, home_form, max_adjustment=Decimal("30"))
                away_elo_adj = apply_form_adjustment(away_elo_adj, away_form, max_adjustment=Decimal("30"))

            # Apply rest adjustment if requested
            if 'rest' in adjustments:
                home_rest_adj = get_rest_adjustment(row['home_rest_days'])
                away_rest_adj = get_rest_adjustment(row['away_rest_days'])
                home_elo_adj += home_rest_adj
                away_elo_adj += away_rest_adj

            # Apply goalie adjustment if requested
            if 'goalies' in adjustments:
                goalie_adj = calculate_goalie_advantage(
                    Decimal(str(row['home_goalie_sv_pct'])) if pd.notna(row['home_goalie_sv_pct']) else None,
                    Decimal(str(row['away_goalie_sv_pct'])) if pd.notna(row['away_goalie_sv_pct']) else None
                )
                home_elo_adj += goalie_adj

            # Apply injury adjustment if requested
            if 'injuries' in adjustments:
                injury_adj = get_injury_adjustment(
                    row['home_recent_injuries'] if pd.notna(row['home_recent_injuries']) else None,
                    row['home_total_injuries'] if pd.notna(row['home_total_injuries']) else None,
                    row['away_recent_injuries'] if pd.notna(row['away_recent_injuries']) else None,
                    row['away_total_injuries'] if pd.notna(row['away_total_injuries']) else None
                )
                home_elo_adj += injury_adj

            # Calculate probability with adjusted ELOs
            prob = calculate_raw_elo_probability(float(home_elo_adj), float(away_elo_adj))
            predictions.append(prob)

    return np.array(predictions)


def main():
    """Test each adjustment individually and compare results."""

    log.info("")
    log.info("=" * 100)
    log.info("INDIVIDUAL ADJUSTMENT TESTING")
    log.info("=" * 100)
    log.info("")
    log.info("Testing each feature adjustment in isolation to determine value.")
    log.info("")

    # Load test set
    log.info("Loading test set game IDs...")
    train_ids, val_ids, test_ids = get_train_val_test_splits('season_based')
    log.info(f"Test set: {len(test_ids)} games")
    log.info("")

    # Load all adjustment data
    log.info("Loading game data with all adjustment features...")
    df = load_all_adjustment_data(test_ids)
    log.info(f"Loaded {len(df)} games with complete data")
    log.info("")

    # Get actual outcomes
    y_true = df['actual_home_win'].values

    # Define models to test
    models = {
        'Baseline (Raw ELO)': [],
        'Raw ELO + Form': ['form'],
        'Raw ELO + Rest': ['rest'],
        'Raw ELO + Goalies': ['goalies'],
        'Raw ELO + Injuries': ['injuries'],
    }

    results = {}

    # Test each model
    log.info("Calculating predictions for each model...")
    log.info("")

    for model_name, adjustments in models.items():
        log.info(f"Testing: {model_name}")

        # Calculate predictions
        predictions = calculate_predictions_with_adjustments(df, adjustments)

        # Calculate metrics
        metrics = calculate_metrics(y_true, predictions)
        results[model_name] = metrics

        log.info(f"  Accuracy:          {metrics['accuracy']:.4f} ({metrics['accuracy']*100:.2f}%)")
        log.info(f"  Brier Score:       {metrics['brier_score']:.4f}")
        log.info(f"  Calibration Error: {metrics['calibration_error']:.4f} ({metrics['calibration_error']*100:.2f}%)")
        log.info("")

    # Comparison table
    log.info("=" * 100)
    log.info("COMPARISON SUMMARY")
    log.info("=" * 100)
    log.info("")

    baseline_metrics = results['Baseline (Raw ELO)']

    log.info(f"{'Model':<30} {'Accuracy':>10} {'Δ Accuracy':>12} {'Brier':>10} {'Δ Brier':>10} {'Cal Error':>12} {'Δ Cal':>10}")
    log.info("-" * 100)

    for model_name, metrics in results.items():
        acc_diff = (metrics['accuracy'] - baseline_metrics['accuracy']) * 100
        brier_diff = baseline_metrics['brier_score'] - metrics['brier_score']  # Lower is better, so flip
        cal_diff = baseline_metrics['calibration_error'] - metrics['calibration_error']  # Lower is better, so flip

        log.info(
            f"{model_name:<30} "
            f"{metrics['accuracy']*100:>9.2f}% "
            f"{acc_diff:>+11.2f}% "
            f"{metrics['brier_score']:>10.4f} "
            f"{brier_diff:>+10.4f} "
            f"{metrics['calibration_error']*100:>11.2f}% "
            f"{cal_diff*100:>+9.2f}%"
        )

    log.info("")
    log.info("=" * 100)
    log.info("INTERPRETATION")
    log.info("=" * 100)
    log.info("")

    # Determine which adjustments help
    helpful_adjustments = []
    harmful_adjustments = []

    for model_name, metrics in results.items():
        if model_name == 'Baseline (Raw ELO)':
            continue

        # Count improvements
        accuracy_better = metrics['accuracy'] > baseline_metrics['accuracy']
        brier_better = metrics['brier_score'] < baseline_metrics['brier_score']
        cal_better = metrics['calibration_error'] < baseline_metrics['calibration_error']

        wins = sum([accuracy_better, brier_better, cal_better])

        adjustment_name = model_name.replace('Raw ELO + ', '')

        if wins >= 2:
            helpful_adjustments.append((adjustment_name, wins))
        else:
            harmful_adjustments.append((adjustment_name, wins))

    # Report findings
    if helpful_adjustments:
        log.info("HELPFUL ADJUSTMENTS (improve 2+ metrics):")
        for adj, wins in helpful_adjustments:
            log.info(f"  ✓ {adj} - improves {wins}/3 metrics")
        log.info("")
    else:
        log.info("NO HELPFUL ADJUSTMENTS FOUND")
        log.info("All adjustments either hurt performance or don't help enough.")
        log.info("")

    if harmful_adjustments:
        log.info("HARMFUL ADJUSTMENTS (improve <2 metrics):")
        for adj, wins in harmful_adjustments:
            log.info(f"  ✗ {adj} - only improves {wins}/3 metrics")
        log.info("")

    # Recommendation
    log.info("=" * 100)
    log.info("RECOMMENDATION")
    log.info("=" * 100)
    log.info("")

    if not helpful_adjustments:
        log.info("RESULT: NONE of the adjustments improve prediction quality.")
        log.info("")
        log.info("Recommendation: Use RAW ELO ONLY")
        log.info("")
        log.info("Next steps:")
        log.info("1. Remove all adjustments from compute_game_pricing_elos.py")
        log.info("2. Use existing Platt parameters for raw ELO (param #3 from original training)")
        log.info("3. Expect realistic edges of 2-5%")
    elif len(helpful_adjustments) < len(models) - 1:  # Not all adjustments helpful
        log.info("RESULT: Only SOME adjustments are valuable.")
        log.info("")
        log.info("Recommendation: Keep only the helpful adjustments:")
        for adj, wins in helpful_adjustments:
            log.info(f"  - {adj}")
        log.info("")
        log.info("Remove the harmful adjustments:")
        for adj, wins in harmful_adjustments:
            log.info(f"  - {adj}")
        log.info("")
        log.info("Next steps:")
        log.info("1. Modify compute_game_pricing_elos.py to only apply helpful adjustments")
        log.info("2. Retrain Platt scaling on new predictions")
        log.info("3. Test again to verify improvement")
    else:
        log.info("RESULT: ALL adjustments are valuable individually.")
        log.info("")
        log.info("This suggests the problem is with how adjustments are COMBINED, not the adjustments themselves.")
        log.info("")
        log.info("Possible issues:")
        log.info("  - Adjustments are being double-counted")
        log.info("  - Scaling factors are too large (±30, ±40 ELO may be too much)")
        log.info("  - Need to tune the adjustment magnitudes")
        log.info("")
        log.info("Next steps:")
        log.info("1. Reduce adjustment magnitudes (try ±15 ELO instead of ±30)")
        log.info("2. Test combined model with reduced adjustments")
        log.info("3. Or: Keep best single adjustment only")

    log.info("")
    log.info("=" * 100)
    log.info("")


if __name__ == "__main__":
    main()
