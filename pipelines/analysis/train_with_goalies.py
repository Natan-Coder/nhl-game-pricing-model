# pipelines/analysis/train_with_goalies.py

import pandas as pd
import logging
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss
from pipelines.common.data_splits import get_train_val_test_splits
from pipelines.common.logging_setup import setup as setup_logging
import psycopg
from pipelines.config import DATABASE_URL


setup_logging("INFO")
log = logging.getLogger(__name__)


def load_data(game_ids):
    """Fetch features and labels for given game_ids"""
    
    query = """
        SELECT
            gf.game_id,
            gf.home_elo,
            gf.away_elo,
            gf.home_elo - gf.away_elo as elo_diff,
            gf.home_goalie_sv_pct,
            gf.away_goalie_sv_pct,
            gf.home_goalie_sv_pct - gf.away_goalie_sv_pct as goalie_sv_pct_diff,
            CASE WHEN gr.home_goals > gr.away_goals THEN 1 ELSE 0 END as home_win
        FROM game_features gf
        INNER JOIN game_results gr ON gr.game_id = gf.game_id
        WHERE gf.game_id = ANY(%s)
          AND gf.home_elo IS NOT NULL
          AND gf.away_elo IS NOT NULL
          AND gf.home_goalie_sv_pct IS NOT NULL
          AND gf.away_goalie_sv_pct IS NOT NULL
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
    
    X = df[['elo_diff', 'goalie_sv_pct_diff']]
    y = df['home_win']
    
    return X, y


def calculate_metrics(y_true, y_pred_proba):
    """
    Calculate model performance metrics.
    
    Args:
        y_true: Actual outcomes (0 or 1)
        y_pred_proba: Predicted probabilities (0.0 to 1.0)
    
    Returns:
        dict with accuracy, brier_score, calibration_error
    """
    
    # 1. Accuracy (convert probabilities to predictions)
    y_pred = (y_pred_proba >= 0.5).astype(int)
    accuracy = accuracy_score(y_true, y_pred)
    
    # 2. Brier Score (already takes probabilities)
    brier = brier_score_loss(y_true, y_pred_proba)
    
    # 3. Calibration Error (needs calculation)
    calibration_error = calculate_calibration_error(y_true, y_pred_proba)
    
    return {
        'accuracy': accuracy,
        'brier_score': brier,
        'calibration_error': calibration_error
        }


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


def main():
    """Train and evaluate model with ELO + goalie features"""
    
    log.info("=" * 80)
    log.info("MODEL WITH GOALIE FEATURES")
    log.info("=" * 80)
    
    # 1. Get data splits
    log.info("Loading train/val/test splits...")
    train_ids, val_ids, test_ids = get_train_val_test_splits('season_based')
    
    # 2. Load data
    log.info(f"Loading data: {len(train_ids)} train, {len(val_ids)} val, {len(test_ids)} test")
    X_train, y_train = load_data(train_ids)
    X_val, y_val = load_data(val_ids)
    X_test, y_test = load_data(test_ids)
    
    # 3. Train model
    log.info("Training logistic regression...")
    model = LogisticRegression(max_iter=1000)
    model.fit(X_train, y_train)
    
    # 4. Evaluate on TEST set
    log.info("Evaluating on test set...")
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    metrics = calculate_metrics(y_test, y_pred_proba)
    
    # 5. Log results
    log.info("")
    log.info("=" * 80)
    log.info("TEST SET RESULTS:")
    log.info(f"  Accuracy:          {metrics['accuracy']:.4f} (target: > 0.53)")
    log.info(f"  Brier Score:       {metrics['brier_score']:.4f} (target: < 0.240)")
    log.info(f"  Calibration Error: {metrics['calibration_error']:.4f} (target: < 0.03)")
    log.info("=" * 80)


if __name__ == "__main__":
    main()