# pipelines/analysis/evaluate_model.py
"""
Model evaluation metrics for ELO predictions.
Analyzes calibration, Brier score, log loss, and ROI.
"""
from __future__ import annotations
import logging
import math
from decimal import Decimal
from typing import List, Tuple
import psycopg

from pipelines.config import DATABASE_URL
from pipelines.common.logging_setup import setup as setup_logging

setup_logging("INFO")
log = logging.getLogger(__name__)


def load_predictions() -> List[Tuple[Decimal, int]]:
    """
    Reconstruct predictions from team_elo_history and game results.
    For each game, get the ELOs at game time and calculate win probability.
    """
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    gr.game_id,
                    gr.home_team,
                    gr.away_team,
                    gr.game_date,
                    gr.home_goals,
                    gr.away_goals,
                    h_elo.elo_rating as home_elo,
                    a_elo.elo_rating as away_elo
                FROM game_results gr
                LEFT JOIN team_elo_history h_elo
                    ON h_elo.team_code = gr.home_team
                    AND h_elo.game_id = gr.game_id
                LEFT JOIN team_elo_history a_elo
                    ON a_elo.team_code = gr.away_team
                    AND a_elo.game_id = gr.game_id
                WHERE gr.home_goals IS NOT NULL
                AND gr.away_goals IS NOT NULL
                AND h_elo.elo_rating IS NOT NULL
                AND a_elo.elo_rating IS NOT NULL
                ORDER BY gr.game_id
            """)
            rows = cur.fetchall()

    predictions = []
    HOME_ADV = Decimal("50")

    for row in rows:
        game_id, home_team, away_team, game_date, home_goals, away_goals, home_elo, away_elo = row

        # Calculate predicted home win probability
        home_elo = Decimal(str(home_elo))
        away_elo = Decimal(str(away_elo))

        # Apply home advantage
        home_elo_adj = home_elo + HOME_ADV

        # Calculate expected win probability (same formula as replay)
        elo_diff = (home_elo_adj - away_elo) / Decimal("400")
        ten_pow = Decimal("10") ** elo_diff
        predicted_home_win = ten_pow / (Decimal("1") + ten_pow)

        # Determine actual result
        actual_home_won = 1 if home_goals > away_goals else 0

        predictions.append((predicted_home_win, actual_home_won))

    log.info(f"Reconstructed {len(predictions)} predictions from ELO history")
    return predictions


def calculate_brier_score(predictions: List[Tuple[Decimal, int]]) -> Decimal:
    """
    Calculate Brier Score: mean squared error of probability predictions.
    Lower is better. 0 = perfect, 0.25 = baseline, 1 = worst.
    """
    if not predictions:
        return Decimal("0")
    
    total_error = Decimal("0")
    
    for pred_prob, actual in predictions:
        # Squared error: (predicted - actual)**2
        error = (pred_prob - Decimal(str(actual))) ** 2
        total_error += error
        
    # Average the squared errors
    brier_score = total_error / Decimal(str(len(predictions)))
    
    return brier_score


def calculate_log_loss(predictions: List[Tuple[Decimal, int]]) -> float:
    """
    Calculate Log Loss (cross-entropy): penalizes confident wrong predictions.
    Lower is better. 0.693 = baseline (50/50), <0.50 = good.
    """
    if not predictions:
        return 0.0
    
    total_loss = 0.0
    epsilon = 1e-15  # Prevent log(0)
    
    for pred_prob, actual in predictions:
        # Convert to float math.log
        p = float(pred_prob)
        
        # Clip probability to avoid log(0)
        p = max(epsilon, min(1 - epsilon, p))
        
        if actual == 1:
            # Home team won: loss = -log(predicted_home_prob)
            loss = -math.log(p)
        else:
            # Home team lost: loss = -long(1 - predicted_home_prob)
            loss = -math.log(1 - p)
            
        total_loss += loss
        
    # Average the losses
    log_loss = total_loss / len(predictions)
    
    return log_loss


def calibration_analysis(predictions: List[Tuple[Decimal, int]], bin_width: Decimal = Decimal("0.05")):
    """
    Analyze calibration: group predictions into bins and compare predicted vs actual win rates.
    
    Args:
        predictions: List of (predicted_prob, actual_result) tuples
        bin_width: Width of probability bins (default 0.05 = 5%)
      
    Returns:
        List of (bin_start, bin_end, avg_predicted, actual_win_rate, count) tuples
    """
    # Create bins from 0.0 to 1.0
    bins = {}
    bin_start = Decimal("0")
    
    while bin_start < Decimal("1"):
        bin_end = bin_start + bin_width
        bins[(bin_start, bin_end)] = {
            'predicted_probs': [],
            'actuals': []
        }
        bin_start = bin_end
        
    # Assign each prediction to a bin
    for pred_prob, actual in predictions:
        for (bin_start, bin_end) in bins.keys():
            if bin_start <= pred_prob < bin_end:
                bins[(bin_start, bin_end)]['predicted_probs'].append(pred_prob)
                bins[(bin_start, bin_end)]['actuals'].append(actual)
                break
                
    # Calculate statistics for each bin
    calibration_data = []
    
    for (bin_start, bin_end), data in sorted(bins.items()):
        if not data['predicted_probs']:
            continue  # Skip empty bins
        
        count = len(data['predicted_probs'])
        avg_predicted = sum(data['predicted_probs']) / Decimal(str(count))
        actual_win_rate = Decimal(str(sum(data['actuals']))) / Decimal(str(count))
        
        calibration_data.append({
            'bin_start': bin_start,
            'bin_end': bin_end,
            'avg_predicted': avg_predicted,
            'actual_win_rate': actual_win_rate,
            'count': count,
            'difference': actual_win_rate - avg_predicted
        })
        
    return calibration_data


def print_report(predictions: List[Tuple[Decimal, int]]):
    """
    Generate and print comprehensive model evaluation report.
    """
    log.info("=" * 80)
    log.info("ELO MODEL EVALUATION REPORT")
    log.info("=" * 80)
    log.info("")
    
    # Overall stats
    total = len(predictions)
    correct = sum(1 for pred, actual in predictions
                  if (pred > Decimal("0.5") and actual == 1) or
                     (pred <= Decimal("0.5") and actual ==0))
    accuracy = (correct / total * 100) if total > 0 else 0
    
    log.info(f"Total Predictions: {total}")
    log.info(f"Correct Predictions: {correct}")
    log.info(f"Simple Accuracy: {accuracy:.2f}%")
    log.info("")
    
    # Brier Score
    brier = calculate_brier_score(predictions)
    log.info("-" * 80)
    log.info("BRIER SCORE (Probability Accuracy)")
    log.info("-" * 80)
    log.info(f"Brier Score: {float(brier):.4f}")
    log.info("")
    log.info("Interpretation:")
    log.info("  0.000 = Perfect predictions")
    log.info("  0.250 = Baseline (always predict 50/50)")
    if brier < Decimal("0.15"):
        log.info(f"  -> EXCELLENT - Your model is highly accurate!")
    elif brier < Decimal("0.20"):
        log.info(f"  -> GOOD - Your model beats the baseline significantly")
    elif brier < Decimal("0.25"):
        log.info(f"  -> DECENT - Your model is better than random")
    else:
        log.info(f"  -> POOR - Model needs improvement")
    log.info("")
    
    # Log Loss
    logloss = calculate_log_loss(predictions)
    log.info("-" * 80)
    log.info("LOG LOSS (Confidence Penalty)")
    log.info("-" * 80)
    log.info(f"Log Loss: {logloss:.4f}")
    log.info("")
    log.info("Interpretation:")
    log.info("  0.693 = Baseline (always predict 50/50)")
    if logloss < 0.40:
        log.info(f"  -> EXCELLENT - Very well-calibrated probabilities")
    elif logloss < 0.50:
        log.info(f"  -> GOOD - Solid probabilistic predictions")
    elif logloss < 0.693:
        log.info(f"  -> DECENT - Better than random")
    else:
        log.info(f"  -> POOR - Overconfident or inaccurate")
    log.info("")
    
    # Calibration Analysis
    calibration_data = calibration_analysis(predictions)
    
    log.info("-" * 80)
    log.info("CALIBRATION ANALYSIS")
    log.info("-" * 80)
    log.info("When you predict X%, do teams actually win X% of the time?")
    log.info("")
    log.info(f"{'Prob Range':<15} {'Predicted':<12} {'Actual':<12} {'Diff':<10} {'Count':<8}")
    log.info("-" * 80)
    
    for bin_data in calibration_data:
        bin_range = f"{float(bin_data['bin_start'])*100:.0f}-{float(bin_data['bin_end'])*100:.0f}%"
        predicted = f"{float(bin_data['avg_predicted'])*100:.1f}%"
        actual = f"{float(bin_data['actual_win_rate'])*100:.1f}%"
        diff = float(bin_data['difference']) * 100
        diff_str = f"{diff:+.1f}%"
        count = bin_data['count']
        
        log.info(f"{bin_range:<15} {predicted:<12} {actual:<12} {diff_str:<10} {count:<8}")
    
    log.info("")
    log.info("Diff = Actual - Predicted")
    log.info("  Positive (+) = Underconfident (reality better than prediction)")
    log.info("  Negative (-) = Overconfident (reality worse than prediction)")
    log.info("")
    
    # Overall calibration assessment
    avg_abs_diff = sum(abs(float(b['difference'])) for b in calibration_data) / len(calibration_data) if calibration_data else 0
    log.info(f"Average Absolute Calibration Error: {avg_abs_diff*100:.2f}%")
    if avg_abs_diff < 0.03:
        log.info("  -> EXCELLENT calibration!")
    elif avg_abs_diff < 0.05:
        log.info("  -> GOOD calibration")
    elif avg_abs_diff < 0.08:
        log.info("  -> DECENT calibration")
    else:
        log.info("  -> POOR calibration - predictions don't match reality")
    
    log.info("")
    log.info("=" * 80)
    
def main():
    """
    Main entry point: load predictions and generate evaluation report.
    """
    log.info("")
    log.info("Loading predictions from ELO replay...")
    log.info("")
    
    predictions = load_predictions()
    
    if not predictions:
        log.error("No predictions found in database!")
        log.error("Run replay_elos.py first to generate predictions.")
        return
    
    print_report(predictions)
    
    log.info("Evaluation complete!")
    log.info("")

if __name__ == "__main__":
    main()
