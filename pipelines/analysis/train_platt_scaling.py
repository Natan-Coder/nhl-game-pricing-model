"""
Phase 2: Platt Scaling Calibration

Goal: Learn a calibration transform that maps raw ELO probabilities to calibrated probabilities

Approach:
1. Train baseline model on training set
2. Generate predictions on validation set
3. Fit Platt scaling: logit(calibrated) = a * logit(raw) + b
4. Evaluate on held-out test set
5. Save calibration parameters for production use

Formula:
    calibrated_prob = sigmoid(a * logit(raw_prob) + b)

Where:
    logit(p) = log(p / (1 - p))
    sigmoid(x) = 1 / (1 + exp(-x))
"""
from __future__ import annotations
import logging
import math
from decimal import Decimal
from typing import List, Tuple
import psycopg
import pandas as pd
from sklearn.linear_model import LogisticRegression

from pipelines.config import DATABASE_URL
from pipelines.common.logging_setup import setup as setup_logging
from pipelines.common.data_splits import get_train_val_test_splits

setup_logging("INFO")
log = logging.getLogger(__name__)


def logit(p: float) -> float:
    """Convert probability to log-odds."""
    if p <= 0.0 or p >= 1.0:
        # Clip to avoid infinities
        p = max(0.001, min(0.999, p))
    return math.log(p / (1 - p))


def sigmoid(x: float) -> float:
    """Convert log-odds to probability."""
    if x > 20:
        return 1.0
    elif x < -20:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


def fit_platt_scaling(probabilities: List[float], outcomes: List[int]) -> Tuple[float, float]:
    """
    Fit Platt Scaling parameters using maximum likelihood estimation.

    Args:
        probabilities: List of raw probabilities
        outcomes: List of actual outcomes (0 or 1)

    Returns: (a, b) parameters where calibrated_prob = sigmoid(a * logit(raw_prob) + b)
    """
    # Convert to log-odds
    log_odds = [logit(p) for p in probabilities]

    # Use simple gradient descent to find optimal a, b
    # Start with a=1, b=0 (identity transform)
    a = 1.0
    b = 0.0
    learning_rate = 0.01
    max_iterations = 1000

    for iteration in range(max_iterations):
        # Calculate gradients
        grad_a = 0.0
        grad_b = 0.0

        for i in range(len(probabilities)):
            x = log_odds[i]
            y = outcomes[i]

            # Predicted probability
            pred = sigmoid(a * x + b)

            # Gradient of log-likelihood
            error = y - pred
            grad_a += error * x
            grad_b += error

        # Update parameters
        a += learning_rate * grad_a
        b += learning_rate * grad_b

        # Calculate log-likelihood for convergence check
        if iteration % 100 == 0:
            log_likelihood = 0.0
            for i in range(len(probabilities)):
                pred = sigmoid(a * log_odds[i] + b)
                pred = max(0.001, min(0.999, pred))  # Clip for numerical stability
                log_likelihood += outcomes[i] * math.log(pred) + (1 - outcomes[i]) * math.log(1 - pred)

            log.info(f"Iteration {iteration}: a={a:.4f}, b={b:.4f}, log_likelihood={log_likelihood:.2f}")

            # Check for convergence
            if abs(grad_a) < 0.01 and abs(grad_b) < 0.01:
                log.info(f"Converged at iteration {iteration}")
                break

    return a, b


def apply_platt_scaling(prob: float, a: float, b: float) -> float:
    """Apply Platt Scaling transform to a probability."""
    return sigmoid(a * logit(prob) + b)


def calculate_calibration_error(y_true, y_pred_proba, bins=10):
    """Calculate mean absolute calibration error"""
    import numpy as np
    
    # Create bins
    bin_edges = np.linspace(0, 1, bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    
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


def load_data(game_ids):
    """Fetch features and labels for given game_ids"""
    
    query = """
            SELECT
                gf.game_id,
                gf.home_elo,
                gf.away_elo,
                gf.home_elo - gf.away_elo as elo_diff,
                gf.home_rest - gf.away_rest as rest_diff,
                gf.home_goalie_gaa - gf.away_goalie_gaa as goalie_gaa_diff,
                CASE WHEN gr.home_goals > gr.away_goals THEN 1 ELSE 0 END as home_win
            FROM game_features gf
                     INNER JOIN game_results gr ON gr.game_id = gf.game_id
            WHERE gf.game_id = ANY(%s)
              AND gf.home_elo IS NOT NULL
              AND gf.away_elo IS NOT NULL
              AND gf.home_rest IS NOT NULL
              AND gf.away_rest IS NOT NULL
              AND gf.home_goalie_gaa IS NOT NULL
              AND gf.away_goalie_gaa IS NOT NULL
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
    
    X = df[['elo_diff', 'rest_diff', 'goalie_gaa_diff']]
    y = df['home_win']
    
    return X, y


def load_live_moneyline_bets() -> Tuple[List[float], List[int]]:
    """Load live moneyline bets with probabilities and outcomes."""
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    b.model_prob,
                    b.outcome,
                    gr.home_goals,
                    gr.away_goals
                FROM bet_log b
                JOIN game_results gr ON b.game_id = gr.game_id
                WHERE b.market = 'moneyline'
                  AND b.bet_status IN ('won', 'lost')
                ORDER BY b.bet_id
            """)
            rows = cur.fetchall()

    probabilities = []
    outcomes = []

    for model_prob, outcome, home_goals, away_goals in rows:
        prob = float(model_prob)

        # Determine actual result
        if outcome == 'home':
            actual = 1 if home_goals > away_goals else 0
        else:  # away
            actual = 1 if away_goals > home_goals else 0

        probabilities.append(prob)
        outcomes.append(actual)

    return probabilities, outcomes


def load_enhanced_predictions(game_ids):
    """
    Load ENHANCED predictions from game_pricing table (includes form, rest, goalies, injuries).
    This is the corrected approach - calibrate what you actually use in production.
    """
    query = """
        SELECT
            gp.p_home_win,
            CASE WHEN gr.home_goals > gr.away_goals THEN 1 ELSE 0 END as home_win
        FROM game_pricing gp
        INNER JOIN game_results gr ON gr.game_id = gp.game_id
        WHERE gp.game_id = ANY(%s)
        ORDER BY gp.game_id
    """

    with psycopg.connect(
            DATABASE_URL,
            sslmode="require",
            prefer_query_mode=None,
            prepare_threshold=None,
            prepared_statement_cache_queries=None,
            ) as conn:
        df = pd.read_sql(query, conn, params=(game_ids,))

    probabilities = df['p_home_win'].values
    outcomes = df['home_win'].values

    return probabilities, outcomes


def train_and_predict() -> Tuple[List[float], List[int], List[float], List[int]]:
    """
    Load ENHANCED predictions from game_features for calibration.

    IMPORTANT: This uses the ENHANCED probabilities (with form, rest, goalies, injuries)
    from the game_features table, NOT raw ELO predictions. This ensures Platt scaling
    is calibrated on the same distribution used in production.

    Returns:
        (val_probs, val_outcomes, test_probs, test_outcomes)
        - val_probs: Validation set predictions (for fitting Platt scaling)
        - val_outcomes: Validation set actual outcomes
        - test_probs: Test set predictions (for evaluating Platt scaling)
        - test_outcomes: Test set actual outcomes
    """

    # 1. Get data splits
    log.info("Loading train/val/test splits...")
    train_ids, val_ids, test_ids = get_train_val_test_splits('season_based')

    # 2. Load data with all features
    log.info("Loading data with ELO + rest + goalie GAA...")
    X_train, y_train = load_data(train_ids)
    X_val, y_val = load_data(val_ids)
    X_test, y_test = load_data(test_ids)
    
    # 3. Train enhanced model
    log.info("Training enhanced model (ELO + rest + goalie GAA)...")
    model = LogisticRegression(max_iter=1000)
    model.fit(X_train, y_train)
    
    # 4. Generate predictions
    val_probs = model.predict_proba(X_val)[:, 1]
    test_probs = model.predict_proba(X_test)[:, 1]
    
    # 5. Return predictions and outcomes
    return val_probs, y_val, test_probs, y_test

# def load_backtest_predictions() -> Tuple[List[float], List[int]]:
#     """Load backtest predictions with probabilities and outcomes."""
#     with psycopg.connect(DATABASE_URL) as conn:
#         with conn.cursor() as cur:
#             cur.execute("""
#                 SELECT
#                     predicted_home_win_prob,
#                     actual_home_won
#                 FROM live_predictions
#                 WHERE actual_home_won IS NOT NULL
#                 ORDER BY game_id
#             """)
#             rows = cur.fetchall()
#
#     probabilities = []
#     outcomes = []
#
#     for prob, outcome in rows:
#         probabilities.append(float(prob))
#         outcomes.append(int(outcome))
#
#     return probabilities, outcomes


def main():
    """Main entry point: Train and validate Platt Scaling."""
    log.info("")
    log.info("=" * 100)
    log.info("PLATT SCALING CALIBRATION - PHASE 1 ELO-ONLY PROBABILITIES")
    log.info("=" * 100)
    log.info("")
    log.info("Goal: Calibrate Phase 1 predictions (with ELO only)")
    log.info("")

    # Load enhanced predictions from game_pricing
    log.info("Loading predictions from production pipeline (game_pricing table)...")
    #val_probs, val_outcomes, test_probs, test_outcomes = train_and_predict()
    import numpy as np
    all_probs, all_outcomes = load_live_moneyline_bets()

    # Convert to numpy arrays
    all_probs = np.array(all_probs)
    all_outcomes = np.array(all_outcomes)

    # Use 80/20 split: first 174 for training Platt, last 44 for testing
    split_point = int(len(all_probs) * 0.8)
    val_probs = all_probs[:split_point]
    val_outcomes = all_outcomes[:split_point]
    test_probs = all_probs[split_point:]
    test_outcomes = all_outcomes[split_point:]
    log.info(f"Validation set: {len(val_probs)} predictions")
    log.info(f"Test set: {len(test_probs)} predictions")
    
    # Calculate calibration before Platt Scaling (on validation set)
    calib_before = calculate_calibration_error(val_outcomes, val_probs)
    log.info(f"Validation Set - Calibration Error (Before): {calib_before*100:.2f}%")
    log.info("")
    
    # Fit Platt Scaling
    log.info("=" * 100)
    log.info("FITTING PLATT SCALING PARAMETERS")
    log.info("=" * 100)
    log.info("")
    a, b = fit_platt_scaling(val_probs, val_outcomes)

    log.info("")
    log.info(f"Optimal Parameters:")
    log.info(f"  a = {a:.4f}")
    log.info(f"  b = {b:.4f}")
    log.info("")
    
    # Apply Platt Scaling to TEST set
    calibrated_test_probs = np.array([apply_platt_scaling(p, a, b) for p in test_probs])

    # Calculate calibration on TEST set (before and after)
    test_calib_before = calculate_calibration_error(test_outcomes, test_probs)
    test_calib_after = calculate_calibration_error(test_outcomes, calibrated_test_probs)
    
    log.info("")
    log.info("=" * 100)
    log.info("TEST SET RESULTS")
    log.info("=" * 100)
    log.info("")
    log.info(f"Calibration Error (Before Platt Scaling): {test_calib_before*100:.2f}%")
    log.info(f"Calibration Error (After Platt Scaling):  {test_calib_after*100:.2f}%")
    log.info(f"Improvement: {(test_calib_before - test_calib_after)*100:+.2f}%")
    log.info("")
    
    
    # Show example transformations
    log.info("=" * 100)
    log.info("EXAMPLE TRANSFORMATIONS")
    log.info("=" * 100)
    log.info("")

    example_probs = [0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65]
    log.info(f"{'Raw Prob':>10} -> {'Calibrated':>12} | {'Difference':>12}")
    log.info("-" * 100)

    for raw_prob in example_probs:
        calibrated = apply_platt_scaling(raw_prob, a, b)
        diff = calibrated - raw_prob
        log.info(f"{raw_prob*100:>9.1f}% -> {calibrated*100:>10.1f}%  | {diff*100:>+10.1f}%")

    log.info("")

    # Analysis
    log.info("=" * 100)
    log.info("INTERPRETATION")
    log.info("=" * 100)
    log.info("")

    if a < 1.0:
        log.info("a < 1.0: The transform COMPRESSES probabilities toward 50%")
        log.info("         This reduces overconfidence in extreme predictions")
    elif a > 1.0:
        log.info("a > 1.0: The transform EXPANDS probabilities away from 50%")
        log.info("         This increases confidence in extreme predictions")
    else:
        log.info("a ≈ 1.0: The transform preserves the original confidence levels")

    log.info("")

    if b < 0:
        log.info("b < 0: The transform shifts probabilities DOWNWARD")
        log.info("       Model is generally overconfident")
    elif b > 0:
        log.info("b > 0: The transform shifts probabilities UPWARD")
        log.info("       Model is generally underconfident")
    else:
        log.info("b ≈ 0: The transform does not shift probabilities")

    log.info("")

    # Final recommendation
    log.info("=" * 100)
    log.info("FINAL RECOMMENDATION")
    log.info("=" * 100)
    log.info("")
    log.info(f"Platt Scaling Parameters:")
    log.info(f"  a = {a:.4f}")
    log.info(f"  b = {b:.4f}")
    log.info("")
    log.info(f"Calibration Improvement: {test_calib_before*100:.2f}% -> {test_calib_after*100:.2f}% ({(test_calib_before-test_calib_after)*100:+.2f}%)")
    log.info("")

    if test_calib_after < 0.08:
        log.info("✅ RECOMMENDED: Implement Platt Scaling in production")
        log.info("")
        log.info("Next Steps:")
        log.info("1. Add calibration function to pipelines/betting/select_bets.py")
        log.info("2. Apply transform to model_prob before calculating edges")
        log.info("3. Forward test for 1-2 weeks")
        log.info("4. Monitor live calibration continuously")
    else:
        log.info("⚠️ WARNING: Platt Scaling did not sufficiently improve calibration")
        log.info("")
        log.info("Consider alternative approaches:")
        log.info("- Increase sample size (collect more moneyline bets)")
        log.info("- Investigate deeper issues (market efficiency, model structure)")
        log.info("- Try ensemble calibration with multiple methods")
    
    # Save parameters to database
    log.info("")
    log.info("=" * 100)
    log.info("SAVING CALIBRATION PARAMETERS")
    log.info("=" * 100)
    log.info("")
    
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO calibration_params (
                    param_name, param_a, param_b, trained_on_n_bets,
                    calibration_error_before, calibration_error_after, notes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING param_id
            """, (
                'platt_scaling_moneyline',
                a,
                b,
                len(val_probs),
                test_calib_before,
                test_calib_after,
                f'Phase 1 ELO-only: Trained on {len(val_probs)} live moneyline bets from Aug-Sept 2026. Calibrated on \
                actual production predictions (ELO-only). Tested on {len(test_probs)} held-out bets.'
            ))
            param_id = cur.fetchone()[0]
            conn.commit()
    
    log.info(f"✅ Saved calibration parameters with ID: {param_id}")
    log.info("")
    log.info("To activate in production, run:")
    log.info(f"  UPDATE calibration_params SET is_active = TRUE WHERE param_id = {param_id};")
    log.info("")
    
    log.info("")
    log.info("=" * 100)
    log.info("")


if __name__ == "__main__":
    main()
