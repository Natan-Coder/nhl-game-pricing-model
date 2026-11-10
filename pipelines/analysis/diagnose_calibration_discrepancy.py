"""
Phase 1: Diagnose Calibration Discrepancy

Goal: Understand why backtest shows 6.11% calibration error but live shows -18%

Investigation Steps:
1. Reproduce backtest calibration on historical data
2. Split backtest by market type (moneyline specifically)
3. Analyze bet selection bias (all predictions vs selected bets)
4. Compare backtest methodology to live performance calculation

Key Questions:
- Is moneyline calibration worse than overall in backtest too?
- Does bet selection process filter out well-calibrated predictions?
- Is there a systematic difference in how we measure backtest vs live?
"""
from __future__ import annotations
import logging
from decimal import Decimal
from typing import List, Tuple, Dict
import psycopg

from pipelines.config import DATABASE_URL
from pipelines.common.logging_setup import setup as setup_logging

setup_logging("INFO")
log = logging.getLogger(__name__)

# Constants
HOME_ADV = Decimal("50")
SCALING_FACTOR = Decimal("400")


def calculate_win_probability(home_elo: Decimal, away_elo: Decimal) -> Decimal:
    """Calculate predicted home win probability from ELO ratings."""
    home_elo_adj = home_elo + HOME_ADV
    elo_diff = (home_elo_adj - away_elo) / SCALING_FACTOR
    ten_pow = Decimal("10") ** elo_diff
    predicted_home_win = ten_pow / (Decimal("1") + ten_pow)
    return predicted_home_win


def load_all_backtest_predictions() -> List[Tuple[Decimal, int, str, str, str]]:
    """
    Load ALL historical predictions from team_elo_history and game results.

    Returns: List of (predicted_prob, actual_result, game_id, home_team, away_team)
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
                ORDER BY gr.game_date, gr.game_id
            """)
            rows = cur.fetchall()

    predictions = []
    for row in rows:
        game_id, home_team, away_team, game_date, home_goals, away_goals, home_elo, away_elo = row

        # Calculate predicted home win probability
        home_elo = Decimal(str(home_elo))
        away_elo = Decimal(str(away_elo))
        predicted_home_win = calculate_win_probability(home_elo, away_elo)

        # Determine actual result
        actual_home_won = 1 if home_goals > away_goals else 0

        predictions.append((predicted_home_win, actual_home_won, game_id, home_team, away_team))

    log.info(f"Loaded {len(predictions)} backtest predictions")
    return predictions


def load_selected_bets() -> List[Tuple[str, str, str, Decimal, Decimal]]:
    """
    Load bets that were actually selected by the betting strategy.

    Returns: List of (game_id, market, outcome, model_prob, edge)
    """
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    game_id,
                    market,
                    outcome,
                    model_prob,
                    edge
                FROM bet_log
                WHERE bet_status IN ('won', 'lost')
                ORDER BY game_id
            """)
            rows = cur.fetchall()

    bets = [(row[0], row[1], row[2], Decimal(str(row[3])), Decimal(str(row[4]))) for row in rows]
    log.info(f"Loaded {len(bets)} selected bets")
    return bets


def calculate_calibration_error(predictions: List[Tuple[Decimal, int]],
                                bin_width: Decimal = Decimal("0.05"),
                                min_samples: int = 5) -> Tuple[Decimal, List[Dict]]:
    """
    Calculate calibration error across probability bins.

    Returns: (average_absolute_error, bin_details)
    """
    if not predictions:
        return Decimal("0"), []

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

    return avg_error, bin_details


def print_calibration_report(title: str, predictions: List[Tuple[Decimal, int]]):
    """Print calibration analysis for a set of predictions."""
    log.info("")
    log.info("=" * 80)
    log.info(title)
    log.info("=" * 80)
    log.info("")

    if not predictions:
        log.info("No predictions available")
        log.info("=" * 80)
        return

    # Overall stats
    total = len(predictions)
    correct = sum(1 for pred, actual in predictions
                  if (pred > Decimal("0.5") and actual == 1) or
                     (pred <= Decimal("0.5") and actual == 0))
    accuracy = (Decimal(str(correct)) / Decimal(str(total)) * 100) if total > 0 else Decimal("0")

    log.info(f"Total Predictions: {total}")
    log.info(f"Correct: {correct}")
    log.info(f"Accuracy: {float(accuracy):.2f}%")
    log.info("")

    # Calibration analysis
    calib_error, bin_details = calculate_calibration_error(predictions)

    log.info(f"{'Prob Range':<15} {'Predicted':<12} {'Actual':<12} {'Diff':<10} {'Count':<8}")
    log.info("-" * 80)

    for bin_data in bin_details:
        bin_range = f"{float(bin_data['bin_start'])*100:.0f}-{float(bin_data['bin_end'])*100:.0f}%"
        predicted = f"{float(bin_data['avg_predicted'])*100:.1f}%"
        actual = f"{float(bin_data['actual_win_rate'])*100:.1f}%"
        diff = float(bin_data['difference']) * 100
        diff_str = f"{diff:+.1f}%"
        count = bin_data['count']

        log.info(f"{bin_range:<15} {predicted:<12} {actual:<12} {diff_str:<10} {count:<8}")

    log.info("")
    log.info(f"Average Absolute Calibration Error: {float(calib_error)*100:.2f}%")
    log.info("")
    log.info("=" * 80)


def analyze_bet_selection_bias(all_predictions: List[Tuple[Decimal, int, str, str, str]],
                               selected_bets: List[Tuple[str, str, str, Decimal, Decimal]]):
    """
    Compare calibration of ALL predictions vs SELECTED bets.
    This reveals if bet selection process filters out well-calibrated predictions.
    """
    log.info("")
    log.info("=" * 80)
    log.info("BET SELECTION BIAS ANALYSIS")
    log.info("=" * 80)
    log.info("")

    # Create a mapping of game_id to predictions
    pred_map = {game_id: (prob, actual, home, away)
                for prob, actual, game_id, home, away in all_predictions}

    # Filter to moneyline bets only
    moneyline_bets = [bet for bet in selected_bets if bet[1] == 'moneyline']

    log.info(f"Total backtest predictions: {len(all_predictions)}")
    log.info(f"Total selected bets: {len(selected_bets)}")
    log.info(f"Moneyline bets: {len(moneyline_bets)}")
    log.info("")

    # For each moneyline bet, find the corresponding prediction
    selected_predictions = []

    for game_id, market, outcome, model_prob, edge in moneyline_bets:
        if game_id not in pred_map:
            continue

        prob, actual, home_team, away_team = pred_map[game_id]

        # Determine if this bet was on home or away
        # outcome is 'home' or 'away'
        if outcome == 'home':
            bet_prob = prob
            bet_actual = actual
        else:  # away
            bet_prob = Decimal("1") - prob
            bet_actual = 1 - actual

        selected_predictions.append((bet_prob, bet_actual))

    log.info(f"Matched {len(selected_predictions)} moneyline bets to backtest predictions")
    log.info("")

    # Compare calibration
    log.info("CALIBRATION COMPARISON:")
    log.info("-" * 80)

    # All predictions (moneyline equivalent)
    all_preds_simple = [(prob, actual) for prob, actual, _, _, _ in all_predictions]
    all_calib_error, _ = calculate_calibration_error(all_preds_simple)

    # Selected bets
    selected_calib_error, _ = calculate_calibration_error(selected_predictions)

    log.info(f"All predictions calibration:      {float(all_calib_error)*100:.2f}%")
    log.info(f"Selected bets calibration:        {float(selected_calib_error)*100:.2f}%")
    log.info(f"Difference:                       {float(selected_calib_error - all_calib_error)*100:+.2f}%")
    log.info("")

    if selected_calib_error > all_calib_error:
        log.info("*** SELECTION BIAS DETECTED ***")
        log.info("Selected bets have WORSE calibration than overall predictions!")
        log.info("This suggests the edge-finding process filters out well-calibrated predictions.")
    else:
        log.info("No significant selection bias detected.")

    log.info("")
    log.info("=" * 80)

    return selected_predictions


def main():
    """
    Phase 1 Investigation: Diagnose the backtest vs live calibration discrepancy.
    """
    log.info("")
    log.info("=" * 100)
    log.info("PHASE 1: CALIBRATION DISCREPANCY DIAGNOSIS")
    log.info("=" * 100)
    log.info("")
    log.info("Goal: Understand why backtest shows 6.11% error but live shows -18% error")
    log.info("")

    # Step 1: Load all backtest predictions
    log.info("Step 1: Loading all backtest predictions...")
    all_predictions = load_all_backtest_predictions()

    # Step 2: Reproduce overall backtest calibration
    print_calibration_report("STEP 2: OVERALL BACKTEST CALIBRATION (Reproduce 6.11%)",
                            [(prob, actual) for prob, actual, _, _, _ in all_predictions])

    # Step 3: Filter to moneyline-like predictions only
    # Since backtest doesn't separate by market, we need to look at specific probability ranges
    # that would typically be bet on moneyline (higher confidence games)

    # Let's look at predictions where model has stronger opinions (>55% or <45%)
    strong_predictions = [(prob, actual) for prob, actual, _, _, _ in all_predictions
                         if prob > Decimal("0.55") or prob < Decimal("0.45")]

    print_calibration_report("STEP 3: HIGH-CONFIDENCE PREDICTIONS (>55% or <45%)",
                            strong_predictions)

    # Step 4: Load actual selected bets and analyze selection bias
    log.info("Step 4: Loading selected bets...")
    selected_bets = load_selected_bets()

    selected_predictions = analyze_bet_selection_bias(all_predictions, selected_bets)

    # Step 5: Detailed calibration on selected moneyline bets
    print_calibration_report("STEP 5: SELECTED MONEYLINE BETS CALIBRATION",
                            selected_predictions)

    # Step 6: Summary and conclusions
    log.info("")
    log.info("=" * 100)
    log.info("PHASE 1 SUMMARY")
    log.info("=" * 100)
    log.info("")
    log.info("Key Findings:")
    log.info("")
    log.info("1. Backtest calibration on all predictions: [see Step 2 above]")
    log.info("2. High-confidence predictions: [see Step 3 above]")
    log.info("3. Selected bets calibration: [see Step 5 above]")
    log.info("")
    log.info("Next Steps:")
    log.info("- If selection bias detected: Bet selection process is filtering poorly")
    log.info("- If high-confidence worse: Model overconfident on strong predictions")
    log.info("- If backtest looks good: Overfitting or market efficiency issue")
    log.info("")
    log.info("=" * 100)
    log.info("")


if __name__ == "__main__":
    main()
