"""
Compare Raw ELO vs Enhanced Predictions

This script evaluates whether the adjustments (form, rest, goalies, injuries)
actually improve prediction quality compared to raw ELO alone.

Metrics compared:
- Accuracy: % of games predicted correctly
- Brier Score: Overall prediction quality (lower is better)
- Calibration Error: How well probabilities match actual frequencies (lower is better)

Output: Determines if adjustments are helping or hurting the model.
"""

import pandas as pd
import numpy as np
import logging
import psycopg
from sklearn.metrics import accuracy_score, brier_score_loss

from pipelines.config import DATABASE_URL
from pipelines.common.data_splits import get_train_val_test_splits
from pipelines.common.logging_setup import setup as setup_logging

setup_logging("INFO")
log = logging.getLogger(__name__)

# ============================================================================
# STEP 1: Calculate Raw ELO Predictions
# ============================================================================

def calculate_raw_elo_probability(home_elo: float, away_elo: float) -> float:
    """
    Calculate win probability using ONLY raw ELO ratings.

    This is the baseline - no adjustments for form, rest, goalies, or injuries.

    Formula: Standard ELO logistic with 50 point home advantage
        prob = 10^(diff/400) / (1 + 10^(diff/400))
        where diff = (home_elo + 50) - away_elo

    Args:
        home_elo: Home team ELO rating
        away_elo: Away team ELO rating

    Returns:
        Probability that home team wins (0.0 to 1.0)
    """
    HOME_ADVANTAGE = 50  # ELO points for home ice
    SCALE = 400          # Standard ELO scale

    # Calculate the ELO difference (home + advantage - away)
    elo_diff = (home_elo + HOME_ADVANTAGE - away_elo) / SCALE

    # Calculate 10^(elo_diff / scale)
    ten_pow = 10 ** elo_diff

    # Return the logistic probability
    return ten_pow / (1 + ten_pow)


# ============================================================================
# STEP 2: Load Data from Database
# ============================================================================

def load_comparison_data(game_ids: list) -> pd.DataFrame:
    """
    Load all data needed for comparison from database.

    For each game in game_ids, we need:
    - Home and away team ELO ratings (to calculate raw predictions)
    - Enhanced predictions from game_pricing table
    - Actual outcomes from game_results table

    Args:
        game_ids: List of game IDs to analyze

    Returns:
        DataFrame with columns:
            - game_id: Game identifier
            - home_elo: Home team ELO rating
            - away_elo: Away team ELO rating
            - enhanced_prob: Home win probability from game_pricing (with adjustments)
            - actual_home_win: 1 if home team won, 0 if lost
    """

    query = """
        SELECT
            gf.game_id,
            gf.home_elo,
            gf.away_elo,
            gp.p_home_win as enhanced_prob,
            CASE WHEN gr.home_goals > gr.away_goals THEN 1 ELSE 0 END as actual_home_win
        FROM game_features gf
        INNER JOIN game_pricing gp ON gp.game_id = gf.game_id
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


# ============================================================================
# STEP 3: Calculate Performance Metrics
# ============================================================================

def calculate_calibration_error(y_true: np.ndarray, y_pred_proba: np.ndarray, bins: int = 10) -> float:
    """
    Calculate mean absolute calibration error.

    This measures how well predicted probabilities match actual frequencies.
    For example, if you predict 70% probability, do 70% of those games actually result in wins?

    This function is ALREADY IMPLEMENTED for you in train_baseline_model.py (line 79-98).
    I've copied it here so you can focus on the comparison logic.
    """
    # Create bins
    bin_edges = np.linspace(0, 1, bins + 1)

    # Digitize predictions into bins
    bin_indices = np.digitize(y_pred_proba, bin_edges[:-1]) - 1

    errors = []
    for i in range(bins):
        mask = bin_indices == i
        if mask.sum() > 0:  # Only if bin has predictions
            avg_pred = y_pred_proba[mask].mean()
            avg_true = y_true[mask].mean()
            errors.append(abs(avg_pred - avg_true))

    return np.mean(errors) if errors else 0.0


def calculate_metrics(y_true: np.ndarray, y_pred_proba: np.ndarray) -> dict:
    """
    Calculate all performance metrics for a set of predictions.

    This function is ALREADY IMPLEMENTED for you in train_baseline_model.py (line 50-76).
    I've copied it here so you have everything in one place.

    Args:
        y_true: Actual outcomes (0 or 1)
        y_pred_proba: Predicted probabilities (0.0 to 1.0)

    Returns:
        dict with keys:
            - accuracy: % correct predictions
            - brier_score: Overall prediction quality
            - calibration_error: Probability calibration quality
    """
    # 1. Accuracy (convert probabilities to predictions)
    y_pred = (y_pred_proba >= 0.5).astype(int)
    accuracy = accuracy_score(y_true, y_pred)

    # 2. Brier Score
    brier = brier_score_loss(y_true, y_pred_proba)

    # 3. Calibration Error
    calibration_error = calculate_calibration_error(y_true, y_pred_proba)

    return {
        'accuracy': accuracy,
        'brier_score': brier,
        'calibration_error': calibration_error
    }


# ============================================================================
# STEP 4: Main Comparison Logic
# ============================================================================

def main():
    """
    Main execution: Compare raw ELO vs enhanced predictions.

    Steps:
    1. Load test set game IDs
    2. Load game data (ELOs, enhanced predictions, actual outcomes)
    3. Calculate raw ELO predictions for each game
    4. Calculate metrics for both raw and enhanced predictions
    5. Compare and report which is better
    """

    log.info("")
    log.info("=" * 100)
    log.info("COMPARISON: Raw ELO vs Enhanced Predictions")
    log.info("=" * 100)
    log.info("")

    # -----------------------------------------------------------------------
    # Step 1: Get test set game IDs
    # -----------------------------------------------------------------------
    log.info("Loading test set game IDs...")

    train_ids, val_ids, test_ids = get_train_val_test_splits('season_based')

    log.info(f"Test set: {len(test_ids)} games")
    log.info("")

    # -----------------------------------------------------------------------
    # Step 2: Load game data
    # -----------------------------------------------------------------------
    log.info("Loading game data from database...")

    df = load_comparison_data(test_ids)

    log.info(f"Loaded {len(df)} games with complete data")
    log.info("")

    # -----------------------------------------------------------------------
    # Step 3: Calculate raw ELO predictions
    # -----------------------------------------------------------------------
    log.info("Calculating raw ELO predictions...")

    df['raw_prob'] = df.apply(
        lambda row: calculate_raw_elo_probability(row['home_elo'], row['away_elo']),
        axis=1
    )

    log.info("Raw ELO predictions calculated")
    log.info("")

    # -----------------------------------------------------------------------
    # Step 4: Evaluate both models
    # -----------------------------------------------------------------------
    log.info("Evaluating model performance...")
    log.info("")

    # Get the actual outcomes
    y_true = df['actual_home_win'].values

    # Get predictions from both models
    raw_predictions = df['raw_prob'].values
    enhanced_predictions = df['enhanced_prob'].values

    # Calculate metrics for raw ELO
    log.info("Raw ELO Model (baseline):")
    raw_metrics = calculate_metrics(y_true, raw_predictions)
    log.info(f"  Accuracy:          {raw_metrics['accuracy']:.4f} ({raw_metrics['accuracy']*100:.2f}%)")
    log.info(f"  Brier Score:       {raw_metrics['brier_score']:.4f}")
    log.info(f"  Calibration Error: {raw_metrics['calibration_error']:.4f} ({raw_metrics['calibration_error']*100:.2f}%)")
    log.info("")

    # Calculate metrics for enhanced predictions
    log.info("Enhanced Model (with form/rest/goalies/injuries):")
    enhanced_metrics = calculate_metrics(y_true, enhanced_predictions)
    log.info(f"  Accuracy:          {enhanced_metrics['accuracy']:.4f} ({enhanced_metrics['accuracy']*100:.2f}%)")
    log.info(f"  Brier Score:       {enhanced_metrics['brier_score']:.4f}")
    log.info(f"  Calibration Error: {enhanced_metrics['calibration_error']:.4f} ({enhanced_metrics['calibration_error']*100:.2f}%)")
    log.info("")

    # -----------------------------------------------------------------------
    # Step 5: Compare and determine winner
    # -----------------------------------------------------------------------
    log.info("=" * 100)
    log.info("COMPARISON RESULTS")
    log.info("=" * 100)
    log.info("")

    # Calculate improvements (positive = enhanced is better)
    accuracy_diff = enhanced_metrics['accuracy'] - raw_metrics['accuracy']
    brier_diff = raw_metrics['brier_score'] - enhanced_metrics['brier_score']  # Lower brier is better, so flip
    calib_diff = raw_metrics['calibration_error'] - enhanced_metrics['calibration_error']  # Lower is better, so flip

    # Print comparison
    log.info(f"Accuracy:          {accuracy_diff*100:+.2f}% {'(enhanced better)' if accuracy_diff > 0 else '(raw ELO better)'}")
    log.info(f"Brier Score:       {brier_diff:+.4f} {'(enhanced better)' if brier_diff > 0 else '(raw ELO better)'}")
    log.info(f"Calibration Error: {calib_diff*100:+.2f}% {'(enhanced better)' if calib_diff > 0 else '(raw ELO better)'}")
    log.info("")

    # Count wins
    wins_enhanced = sum([
        accuracy_diff > 0,      # Enhanced has higher accuracy
        brier_diff > 0,         # Enhanced has lower brier (better)
        calib_diff > 0          # Enhanced has lower calibration error (better)
    ])

    wins_raw = 3 - wins_enhanced

    log.info(f"Score: Enhanced wins {wins_enhanced}/3 metrics, Raw ELO wins {wins_raw}/3 metrics")
    log.info("")

    log.info("=" * 100)
    log.info("RECOMMENDATION")
    log.info("=" * 100)
    log.info("")

    if wins_enhanced >= 2:
        log.info("RESULT: Enhanced predictions (with adjustments) perform BETTER")
        log.info("")
        log.info("The adjustments for form, rest, goalies, and injuries are adding value.")
        log.info("However, they still need proper calibration via Platt scaling.")
        log.info("")
        log.info("Next steps:")
        log.info("1. Keep using enhanced predictions")
        log.info("2. Current Platt scaling (param #5) is properly trained on enhanced predictions")
        log.info("3. The high edges you're seeing may be due to:")
        log.info("   - Market inefficiency (unlikely given market efficiency)")
        log.info("   - Overfitting in the adjustments (need to investigate individual adjustments)")
        log.info("   - Need more data for calibration")
    else:
        log.info("RESULT: Raw ELO performs BETTER than enhanced predictions")
        log.info("")
        log.info("The adjustments are adding NOISE, not signal.")
        log.info("")
        log.info("Recommendation: Remove all adjustments and use RAW ELO only")
        log.info("")
        log.info("Next steps:")
        log.info("1. Modify compute_game_pricing_elos.py to remove adjustments")
        log.info("2. Retrain Platt scaling on raw ELO predictions")
        log.info("3. Edges should drop to realistic 1-5% range")
        log.info("4. Start live betting with small stakes")

    log.info("")
    log.info("=" * 100)
    log.info("")


if __name__ == "__main__":
    main()
