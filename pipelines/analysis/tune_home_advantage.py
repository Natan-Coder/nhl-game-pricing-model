"""
Phase 2: HOME_ADV Grid Search

Goal: Find optimal HOME_ADV value that minimizes calibration error on moneyline predictions

Approach:
1. Grid search HOME_ADV from 25 to 60 in steps of 5
2. For each value, calculate win probabilities and calibration error
3. Focus on high-confidence predictions (where moneyline bets typically occur)
4. Select value that minimizes calibration error
5. Validate on held-out test set
"""
from __future__ import annotations
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Tuple, Dict
import psycopg

from pipelines.config import DATABASE_URL
from pipelines.common.logging_setup import setup as setup_logging

setup_logging("INFO")
log = logging.getLogger(__name__)

# Constants
SCALING_FACTOR = Decimal("400")


def calculate_win_probability(home_elo: Decimal, away_elo: Decimal, home_adv: Decimal) -> Decimal:
    """Calculate predicted home win probability from ELO ratings with given HOME_ADV."""
    home_elo_adj = home_elo + home_adv
    elo_diff = (home_elo_adj - away_elo) / SCALING_FACTOR
    ten_pow = Decimal("10") ** elo_diff
    predicted_home_win = ten_pow / (Decimal("1") + ten_pow)
    return predicted_home_win


def load_historical_games(cutoff_date: str = None) -> List[Tuple]:
    """
    Load historical games with ELO ratings.

    Args:
        cutoff_date: If provided, only load games before this date (for train/test split)

    Returns: List of (game_id, home_elo, away_elo, home_goals, away_goals, game_date)
    """
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            if cutoff_date:
                cur.execute("""
                    SELECT
                        gr.game_id,
                        h_elo.elo_rating as home_elo,
                        a_elo.elo_rating as away_elo,
                        gr.home_goals,
                        gr.away_goals,
                        gr.game_date
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
                    AND gr.game_date < %s
                    ORDER BY gr.game_date, gr.game_id
                """, (cutoff_date,))
            else:
                cur.execute("""
                    SELECT
                        gr.game_id,
                        h_elo.elo_rating as home_elo,
                        a_elo.elo_rating as away_elo,
                        gr.home_goals,
                        gr.away_goals,
                        gr.game_date
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
                    ORDER BY gr.game_date, gr.game_id
                """)
            rows = cur.fetchall()

    return rows


def calculate_calibration_error(predictions: List[Tuple[Decimal, int]],
                                bin_width: Decimal = Decimal("0.05"),
                                min_samples: int = 5) -> Tuple[Decimal, List[Dict], Decimal]:
    """
    Calculate calibration error across probability bins.

    Returns: (average_absolute_error, bin_details, accuracy)
    """
    if not predictions:
        return Decimal("0"), [], Decimal("0")

    # Create bins
    bins = {}
    bin_start = Decimal("0")

    while bin_start < Decimal("1"):
        bin_end = bin_start + bin_width
        bins[(bin_start, bin_end)] = {
            'predicted_probs': [],
            'actuals': []
        }
        bin_start = bin_end

    # Assign predictions to bins
    for pred_prob, actual in predictions:
        for (bin_start, bin_end) in bins.keys():
            if bin_start <= pred_prob < bin_end:
                bins[(bin_start, bin_end)]['predicted_probs'].append(pred_prob)
                bins[(bin_start, bin_end)]['actuals'].append(actual)
                break

    # Calculate statistics for each bin
    bin_details = []
    errors = []

    for (bin_start, bin_end), data in sorted(bins.items()):
        if len(data['predicted_probs']) < min_samples:
            continue  # Skip bins with too few samples

        count = len(data['predicted_probs'])
        avg_predicted = sum(data['predicted_probs']) / Decimal(str(count))
        actual_win_rate = Decimal(str(sum(data['actuals']))) / Decimal(str(count))
        difference = actual_win_rate - avg_predicted

        bin_details.append({
            'bin_start': bin_start,
            'bin_end': bin_end,
            'avg_predicted': avg_predicted,
            'actual_win_rate': actual_win_rate,
            'count': count,
            'difference': difference
        })

        errors.append(abs(difference))

    avg_error = sum(errors) / len(errors) if errors else Decimal("0")

    # Calculate accuracy
    total = len(predictions)
    correct = sum(1 for pred, actual in predictions
                  if (pred > Decimal("0.5") and actual == 1) or
                     (pred <= Decimal("0.5") and actual == 0))
    accuracy = Decimal(str(correct)) / Decimal(str(total)) if total > 0 else Decimal("0")

    return avg_error, bin_details, accuracy


def evaluate_home_adv(games: List[Tuple], home_adv: Decimal,
                     filter_high_confidence: bool = False) -> Dict:
    """
    Evaluate calibration for a given HOME_ADV value.

    Args:
        games: List of (game_id, home_elo, away_elo, home_goals, away_goals, game_date)
        home_adv: HOME_ADV value to test
        filter_high_confidence: If True, only evaluate high-confidence predictions

    Returns: Dict with calibration metrics
    """
    predictions = []

    for game_id, home_elo, away_elo, home_goals, away_goals, game_date in games:
        home_elo = Decimal(str(home_elo))
        away_elo = Decimal(str(away_elo))

        # Calculate predicted probability
        pred_prob = calculate_win_probability(home_elo, away_elo, home_adv)

        # Actual result
        actual_home_won = 1 if home_goals > away_goals else 0

        # Filter for high-confidence if requested (simulates moneyline betting)
        if filter_high_confidence:
            if pred_prob < Decimal("0.45") or pred_prob > Decimal("0.55"):
                predictions.append((pred_prob, actual_home_won))
        else:
            predictions.append((pred_prob, actual_home_won))

    # Calculate calibration
    calib_error, bin_details, accuracy = calculate_calibration_error(predictions)

    return {
        'home_adv': home_adv,
        'num_predictions': len(predictions),
        'calibration_error': calib_error,
        'accuracy': accuracy,
        'bin_details': bin_details
    }


def grid_search_home_adv(games: List[Tuple],
                        min_adv: int = 25,
                        max_adv: int = 60,
                        step: int = 5,
                        filter_high_confidence: bool = False) -> List[Dict]:
    """
    Grid search over HOME_ADV values.

    Returns: List of evaluation results for each HOME_ADV value
    """
    results = []

    for adv in range(min_adv, max_adv + 1, step):
        home_adv = Decimal(str(adv))
        result = evaluate_home_adv(games, home_adv, filter_high_confidence)
        results.append(result)

        log.info(f"HOME_ADV={adv:2d}: {result['num_predictions']} predictions, "
                f"calibration={float(result['calibration_error'])*100:.2f}%, "
                f"accuracy={float(result['accuracy'])*100:.2f}%")

    return results


def print_grid_search_results(results: List[Dict], title: str = "Grid Search Results"):
    """Print formatted grid search results."""
    log.info("")
    log.info("=" * 100)
    log.info(title)
    log.info("=" * 100)
    log.info("")

    log.info(f"{'HOME_ADV':<10} | {'Predictions':<12} | {'Calibration':>12} | {'Accuracy':>10} | {'Assessment':<15}")
    log.info("-" * 100)

    for result in results:
        home_adv = int(result['home_adv'])
        num_preds = result['num_predictions']
        calib_error = float(result['calibration_error']) * 100
        accuracy = float(result['accuracy']) * 100

        # Assessment
        if calib_error < 3.0:
            assessment = "EXCELLENT"
        elif calib_error < 5.0:
            assessment = "GOOD"
        elif calib_error < 8.0:
            assessment = "MODERATE"
        else:
            assessment = "POOR"

        log.info(f"{home_adv:<10} | {num_preds:<12} | {calib_error:>11.2f}% | {accuracy:>9.2f}% | {assessment:<15}")

    log.info("")

    # Find optimal
    optimal = min(results, key=lambda x: x['calibration_error'])
    log.info(f"OPTIMAL HOME_ADV: {int(optimal['home_adv'])}")
    log.info(f"  Calibration Error: {float(optimal['calibration_error'])*100:.2f}%")
    log.info(f"  Accuracy: {float(optimal['accuracy'])*100:.2f}%")
    log.info(f"  Predictions: {optimal['num_predictions']}")
    log.info("")
    log.info("=" * 100)


def print_detailed_calibration(result: Dict):
    """Print detailed calibration table for a specific HOME_ADV value."""
    log.info("")
    log.info("=" * 100)
    log.info(f"DETAILED CALIBRATION: HOME_ADV = {int(result['home_adv'])}")
    log.info("=" * 100)
    log.info("")

    log.info(f"{'Prob Range':<15} {'Predicted':<12} {'Actual':<12} {'Diff':<10} {'Count':<8}")
    log.info("-" * 100)

    for bin_data in result['bin_details']:
        bin_range = f"{float(bin_data['bin_start'])*100:.0f}-{float(bin_data['bin_end'])*100:.0f}%"
        predicted = f"{float(bin_data['avg_predicted'])*100:.1f}%"
        actual = f"{float(bin_data['actual_win_rate'])*100:.1f}%"
        diff = float(bin_data['difference']) * 100
        diff_str = f"{diff:+.1f}%"
        count = bin_data['count']

        log.info(f"{bin_range:<15} {predicted:<12} {actual:<12} {diff_str:<10} {count:<8}")

    log.info("")
    log.info(f"Overall Calibration Error: {float(result['calibration_error'])*100:.2f}%")
    log.info(f"Accuracy: {float(result['accuracy'])*100:.2f}%")
    log.info("")
    log.info("=" * 100)


def main():
    """
    Main entry point: Grid search for optimal HOME_ADV value.
    """
    log.info("")
    log.info("=" * 100)
    log.info("PHASE 2: HOME_ADV GRID SEARCH")
    log.info("=" * 100)
    log.info("")
    log.info("Goal: Find optimal HOME_ADV that minimizes calibration error")
    log.info("")

    # Load historical games
    log.info("Loading historical games...")
    all_games = load_historical_games()
    log.info(f"Loaded {len(all_games)} historical games")
    log.info("")

    # Split into train/test (use games before Nov 1, 2025 for tuning)
    train_cutoff_str = "2025-11-01"
    train_cutoff = datetime.strptime(train_cutoff_str, "%Y-%m-%d").date()
    train_games = [g for g in all_games if g[5] < train_cutoff]
    test_games = [g for g in all_games if g[5] >= train_cutoff]

    log.info(f"Train set: {len(train_games)} games (before {train_cutoff})")
    log.info(f"Test set: {len(test_games)} games (after {train_cutoff})")
    log.info("")

    # Grid search on ALL predictions (train set)
    log.info("=" * 100)
    log.info("STEP 1: Grid Search on ALL Predictions (Train Set)")
    log.info("=" * 100)
    log.info("")

    train_results_all = grid_search_home_adv(train_games, min_adv=25, max_adv=60, step=5,
                                             filter_high_confidence=False)

    print_grid_search_results(train_results_all, "Grid Search Results - ALL Predictions (Train)")

    # Grid search on HIGH-CONFIDENCE predictions only (simulates moneyline betting)
    log.info("")
    log.info("=" * 100)
    log.info("STEP 2: Grid Search on HIGH-CONFIDENCE Predictions (Train Set)")
    log.info("=" * 100)
    log.info("(Filtered to >55% or <45% - simulates moneyline betting scenarios)")
    log.info("")

    train_results_hc = grid_search_home_adv(train_games, min_adv=25, max_adv=60, step=5,
                                            filter_high_confidence=True)

    print_grid_search_results(train_results_hc, "Grid Search Results - HIGH-CONFIDENCE Predictions (Train)")

    # Find optimal from high-confidence search
    optimal_hc = min(train_results_hc, key=lambda x: x['calibration_error'])
    optimal_home_adv = optimal_hc['home_adv']

    log.info("")
    log.info("=" * 100)
    log.info("STEP 3: Detailed Calibration for Optimal HOME_ADV")
    log.info("=" * 100)

    print_detailed_calibration(optimal_hc)

    # Validate on test set
    log.info("")
    log.info("=" * 100)
    log.info("STEP 4: Validation on Test Set (Nov 1 - Dec 12, 2025)")
    log.info("=" * 100)
    log.info("")

    # Test with current HOME_ADV = 50
    current_result = evaluate_home_adv(test_games, Decimal("50"), filter_high_confidence=True)
    log.info(f"Current HOME_ADV=50:")
    log.info(f"  Calibration Error: {float(current_result['calibration_error'])*100:.2f}%")
    log.info(f"  Accuracy: {float(current_result['accuracy'])*100:.2f}%")
    log.info(f"  Predictions: {current_result['num_predictions']}")
    log.info("")

    # Test with optimal HOME_ADV
    optimal_result = evaluate_home_adv(test_games, optimal_home_adv, filter_high_confidence=True)
    log.info(f"Optimal HOME_ADV={int(optimal_home_adv)}:")
    log.info(f"  Calibration Error: {float(optimal_result['calibration_error'])*100:.2f}%")
    log.info(f"  Accuracy: {float(optimal_result['accuracy'])*100:.2f}%")
    log.info(f"  Predictions: {optimal_result['num_predictions']}")
    log.info("")

    # Calculate improvement
    improvement = current_result['calibration_error'] - optimal_result['calibration_error']
    log.info(f"Improvement: {float(improvement)*100:+.2f}% calibration error")
    log.info("")

    print_detailed_calibration(optimal_result)

    # Final recommendation
    log.info("")
    log.info("=" * 100)
    log.info("FINAL RECOMMENDATION")
    log.info("=" * 100)
    log.info("")
    log.info(f"Current HOME_ADV: 50")
    log.info(f"Recommended HOME_ADV: {int(optimal_home_adv)}")
    log.info("")
    log.info("Expected Impact:")
    log.info(f"  Calibration Error: {float(current_result['calibration_error'])*100:.2f}% -> "
            f"{float(optimal_result['calibration_error'])*100:.2f}% ({float(improvement)*100:+.2f}%)")
    log.info(f"  Accuracy: {float(current_result['accuracy'])*100:.2f}% -> "
            f"{float(optimal_result['accuracy'])*100:.2f}%")
    log.info("")
    log.info("Next Steps:")
    log.info("1. Update HOME_ADVANTAGE in pipelines/pricing/compute_game_pricing_elos.py")
    log.info("2. Update HOME_ADV in pipelines/pricing/compute_team_elos.py")
    log.info("3. Re-run ELO replay to regenerate historical ELOs with new value")
    log.info("4. Forward test with paper trading for 1-2 weeks")
    log.info("5. Gradual rollout with minimum stakes")
    log.info("")
    log.info("=" * 100)
    log.info("")


if __name__ == "__main__":
    main()
