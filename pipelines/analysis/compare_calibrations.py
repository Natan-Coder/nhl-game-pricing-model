"""
Compare different calibration parameter sets on the same test data.

This script:
1. Loads the test set
2. Trains baseline model on train set
3. Gets raw predictions on test set
4. Applies each calibration transform
5. Compares all metrics side-by-side
"""
import logging
import math
import psycopg
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss

from pipelines.config import DATABASE_URL
from pipelines.common.logging_setup import setup as setup_logging
from pipelines.common.data_splits import get_train_val_test_splits

setup_logging("INFO")
log = logging.getLogger(__name__)


def logit(p: float) -> float:
    """Convert probability to log-odds."""
    if p <= 0.0 or p >= 1.0:
        p = max(0.001, min(0.999, p))
    return math.log(p / (1 - p))


def sigmoid(x: float) -> float:
    """Convert log-odds to probability."""
    if x > 20:
        return 1.0
    elif x < -20:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


def apply_platt_scaling(prob: float, a: float, b: float) -> float:
    """Apply Platt Scaling transform to a probability."""
    return sigmoid(a * logit(prob) + b)


def calculate_calibration_error(y_true, y_pred_proba, bins=10):
    """Calculate mean absolute calibration error"""
    # Create bins
    bin_edges = np.linspace(0, 1, bins + 1)

    # Digitize predictions into bins
    bin_indices = np.digitize(y_pred_proba, bin_edges[:-1]) - 1

    errors = []
    for i in range(bins):
        mask = bin_indices == i
        if mask.sum() > 0:
            avg_pred = y_pred_proba[mask].mean()
            avg_true = y_true[mask].mean()
            errors.append(abs(avg_pred - avg_true))

    return np.mean(errors) if errors else 0.0


def load_data(game_ids):
    """Fetch features and labels for given game_ids"""
    query = """
        SELECT
            gf.game_id,
            gf.home_elo - gf.away_elo as elo_diff,
            CASE WHEN gr.home_goals > gr.away_goals THEN 1 ELSE 0 END as home_win
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
        prepare_threshold=None,
    ) as conn:
        df = pd.read_sql(query, conn, params=(game_ids,))

    X = df[['elo_diff']]
    y = df['home_win']

    return X, y


def load_calibration_params():
    """Load all calibration parameters from database"""
    with psycopg.connect(DATABASE_URL, sslmode='require', prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    param_id,
                    param_a,
                    param_b,
                    param_name,
                    is_active
                FROM calibration_params
                ORDER BY param_id
            """)
            rows = cur.fetchall()

    params = []
    for row in rows:
        params.append({
            'param_id': row[0],
            'a': float(row[1]),
            'b': float(row[2]),
            'name': row[3],
            'is_active': row[4]
        })

    return params


def calculate_metrics(y_true, y_pred_proba):
    """Calculate all performance metrics"""
    y_pred = (y_pred_proba >= 0.5).astype(int)

    return {
        'accuracy': accuracy_score(y_true, y_pred),
        'brier_score': brier_score_loss(y_true, y_pred_proba),
        'calibration_error': calculate_calibration_error(y_true, y_pred_proba),
        'min_prob': np.min(y_pred_proba),
        'max_prob': np.max(y_pred_proba),
        'mean_prob': np.mean(y_pred_proba),
        'std_prob': np.std(y_pred_proba)
    }


def main():
    log.info("=" * 100)
    log.info("CALIBRATION PARAMETER COMPARISON")
    log.info("=" * 100)
    log.info("")

    # 1. Load data splits
    log.info("Loading data splits...")
    train_ids, val_ids, test_ids = get_train_val_test_splits('season_based')

    # 2. Train baseline model
    log.info(f"Training baseline model on {len(train_ids)} games...")
    X_train, y_train = load_data(train_ids)
    X_test, y_test = load_data(test_ids)

    model = LogisticRegression(max_iter=1000)
    model.fit(X_train, y_train)

    # 3. Get raw predictions on test set
    log.info(f"Generating predictions on {len(test_ids)} test games...")
    raw_probs = model.predict_proba(X_test)[:, 1]

    # 4. Load all calibration parameters
    log.info("Loading calibration parameters...")
    all_params = load_calibration_params()
    log.info(f"Found {len(all_params)} calibration parameter sets")
    log.info("")

    # 5. Calculate metrics for raw (no calibration)
    log.info("=" * 100)
    log.info("BASELINE (NO CALIBRATION)")
    log.info("=" * 100)
    raw_metrics = calculate_metrics(y_test, raw_probs)
    log.info(f"  Accuracy:          {raw_metrics['accuracy']:.4f}")
    log.info(f"  Brier Score:       {raw_metrics['brier_score']:.4f}")
    log.info(f"  Calibration Error: {raw_metrics['calibration_error']:.4f} ({raw_metrics['calibration_error']*100:.2f}%)")
    log.info(f"  Probability Range: {raw_metrics['min_prob']:.4f} - {raw_metrics['max_prob']:.4f}")
    log.info(f"  Probability Std:   {raw_metrics['std_prob']:.4f}")
    log.info("")

    # 6. Calculate metrics for each calibration
    results = []
    results.append({
        'param_id': 'RAW',
        'a': 1.0,
        'b': 0.0,
        'is_active': False,
        'metrics': raw_metrics
    })

    for param_set in all_params:
        log.info("=" * 100)
        log.info(f"PARAM ID {param_set['param_id']} (a={param_set['a']:.4f}, b={param_set['b']:.4f})")
        if param_set['is_active']:
            log.info("*** CURRENTLY ACTIVE IN PRODUCTION ***")
        log.info("=" * 100)

        # Apply calibration
        calibrated_probs = np.array([
            apply_platt_scaling(p, param_set['a'], param_set['b'])
            for p in raw_probs
        ])

        # Calculate metrics
        metrics = calculate_metrics(y_test, calibrated_probs)

        log.info(f"  Accuracy:          {metrics['accuracy']:.4f}")
        log.info(f"  Brier Score:       {metrics['brier_score']:.4f}")
        log.info(f"  Calibration Error: {metrics['calibration_error']:.4f} ({metrics['calibration_error']*100:.2f}%)")
        log.info(f"  Probability Range: {metrics['min_prob']:.4f} - {metrics['max_prob']:.4f}")
        log.info(f"  Probability Std:   {metrics['std_prob']:.4f}")
        log.info("")

        results.append({
            'param_id': param_set['param_id'],
            'a': param_set['a'],
            'b': param_set['b'],
            'is_active': param_set['is_active'],
            'metrics': metrics
        })

    # 7. Summary comparison table
    log.info("=" * 100)
    log.info("SUMMARY COMPARISON")
    log.info("=" * 100)
    log.info("")

    print("\n" + "=" * 130)
    print(f"{'ID':^6} | {'a':^8} | {'b':^9} | {'Active':^7} | {'Accuracy':^10} | {'Brier':^8} | {'Cal Err':^9} | {'Prob Range':^18} | {'Prob Std':^9}")
    print("-" * 130)

    for result in results:
        active_str = 'YES' if result['is_active'] else ''
        m = result['metrics']
        prob_range = f"{m['min_prob']:.3f}-{m['max_prob']:.3f}"

        print(f"{str(result['param_id']):^6} | {result['a']:8.4f} | {result['b']:9.4f} | {active_str:^7} | "
              f"{m['accuracy']:10.4f} | {m['brier_score']:8.4f} | {m['calibration_error']*100:8.2f}% | "
              f"{prob_range:^18} | {m['std_prob']:9.4f}")

    print("=" * 130)
    print("\nKEY METRICS:")
    print("  - Calibration Error: Lower is better (target: <3.0%)")
    print("  - Brier Score: Lower is better (target: <0.240)")
    print("  - Accuracy: Higher is better (target: >53%)")
    print("  - Prob Std: Higher = more discriminative (can identify strong favorites)")
    print("=" * 130)

    # 8. Recommendations
    log.info("")
    log.info("=" * 100)
    log.info("RECOMMENDATIONS")
    log.info("=" * 100)
    log.info("")

    # Find best by each metric
    best_cal = min(results, key=lambda x: x['metrics']['calibration_error'])
    best_brier = min(results, key=lambda x: x['metrics']['brier_score'])
    best_acc = max(results, key=lambda x: x['metrics']['accuracy'])
    most_disc = max(results, key=lambda x: x['metrics']['std_prob'])

    log.info(f"Best Calibration:    Param ID {best_cal['param_id']} ({best_cal['metrics']['calibration_error']*100:.2f}%)")
    log.info(f"Best Brier Score:    Param ID {best_brier['param_id']} ({best_brier['metrics']['brier_score']:.4f})")
    log.info(f"Best Accuracy:       Param ID {best_acc['param_id']} ({best_acc['metrics']['accuracy']:.4f})")
    log.info(f"Most Discriminative: Param ID {most_disc['param_id']} (std={most_disc['metrics']['std_prob']:.4f})")
    log.info("")

    # Overall recommendation
    log.info("OVERALL RECOMMENDATION:")
    log.info("")

    # Check if any param meets all targets
    for result in results:
        m = result['metrics']
        meets_cal = m['calibration_error'] < 0.05  # <5% is acceptable
        meets_brier = m['brier_score'] < 0.250
        meets_acc = m['accuracy'] > 0.53

        if meets_cal and meets_brier and meets_acc:
            log.info(f"  Param ID {result['param_id']} meets all targets:")
            log.info(f"    - Calibration: {m['calibration_error']*100:.2f}% (target: <5%)")
            log.info(f"    - Brier:       {m['brier_score']:.4f} (target: <0.250)")
            log.info(f"    - Accuracy:    {m['accuracy']:.4f} (target: >0.53)")
            log.info("")

    log.info("=" * 100)


if __name__ == "__main__":
    main()
