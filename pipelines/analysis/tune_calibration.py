# pipelines/analysis/tune_calibration.py
"""
Calibration Parameter Tuning

Tests different combinations of home advantage and K-factor to find
the configuration that produces the best-calibrated probabilities.

Goal: Minimize calibration error (predicted % should match actual %)
"""
from __future__ import annotations
import logging
from datetime import date
from decimal import Decimal, getcontext
from typing import List, Tuple, Dict
from collections import defaultdict

from pipelines.config import DATABASE_URL
from pipelines.common.db import connect
from pipelines.common.logging_setup import setup as setup_logging

setup_logging("INFO")
getcontext().prec = 28  # High precision for Decimal calculations
log = logging.getLogger(__name__)


def replay_with_params(
    home_advantage: Decimal,
    k_factor: Decimal,
    start_date: str = "2024-10-01",
    end_date: str = "2025-06-30"
) -> List[Tuple[Decimal, int]]:
    """
    Run ELO replay with specified parameters.
    
    Args:
        home_advantage: ELO points to add for home ice advantage
        k_factor: Rating update strength after each game
        start_date: Start date for replay
        end_date: End date for replay
        
    Returns:
        List of (predicted_prob, actual_result) tuples
    """
    # Initialize all teams at 1500 ELO
    team_elos: Dict[str, Decimal] = defaultdict(lambda: Decimal("1500"))
    
    # Load games chronologically
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    gr.game_id,
                    gr.game_date,
                    gr.home_team,
                    gr.away_team,
                    gr.home_goals,
                    gr.away_goals
                FROM game_results gr
                WHERE gr.game_date >= %s
                AND gr.game_date <= %s
                AND gr.home_goals IS NOT NULL
                AND gr.away_goals IS NOT NULL
                ORDER BY gr.game_date, gr.game_id
            """, (start_date, end_date))
            games = cur.fetchall()
            
    predictions = []
    
    for game in games:
        game_id, game_date, home_team, away_team, home_goals, away_goals = game
        
        # Get current ELOs
        home_elo = team_elos[home_team]
        away_elo = team_elos[away_team]
        
        # Calculate predicted home win probability
        home_elo_adj = home_elo + home_advantage
        elo_diff = (home_elo_adj - away_elo) / Decimal("400")
        ten_pow = Decimal("10") ** elo_diff
        predicted_home_win = ten_pow / (Decimal("1") + ten_pow)
        
        # Actual result
        actual_home_won = 1 if home_goals > away_goals else 0
        
        # Store prediction
        predictions.append((predicted_home_win, actual_home_won))
        
        # Update ELOs based on result
        expected_home = predicted_home_win
        actual_home = Decimal("1.0") if home_goals > away_goals else Decimal("0.0")
        
        # Apply home advantage for expected calculation
        expected_away = Decimal("1") - expected_home
        actual_away = Decimal("1.0") - actual_home
        
        # Update ratings
        team_elos[home_team] = home_elo + k_factor + (actual_home - expected_home)
        team_elos[away_team] = away_elo + k_factor + (actual_away - expected_away)
        
    return predictions


def evaluate_calibration(predictions: List[Tuple[Decimal, int]]) -> Decimal:
    """
    Calculate average absolute calibration error.
    
    Bins predictions and measures how far predicted % differs from actual %.
    Lower is better (0 = perfect calibration).
    
    Args:
        predictions: List of (predicted_prob, actual_result) tuples
    
    Returns:
        Average absolute calibration error (0.0 to 1.0)
    """
    if not predictions:
        return Decimal("999")  # Return high error if no predictions
    
    # Create bins (5% width: 0-5%, 5-10%, ..., 95-100%)
    bin_width = Decimal("0.05")
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
                
    # Calculate calibration error for each bin
    total_abs_error = Decimal("0")
    bin_count = 0
    
    for (bin_start, bin_end), data in bins.items():
        if not data['predicted_probs']:
            continue  # Skip empty bins
            
        # Average predicted probability in this bin
        avg_predicted = sum(data['predicted_probs']) / Decimal(str(len(data['predicted_probs'])))
        
        # Actual win rate in this bin
        actual_win_rate = Decimal(str(sum(data['actuals']))) / Decimal(str(len(data['actuals'])))
        
        # Absolute difference
        abs_error = abs(actual_win_rate - avg_predicted)
        
        total_abs_error += abs_error
        bin_count += 1
        
    # Average error across all bins
    if bin_count == 0:
        return Decimal("999")
    
    avg_calibration_error = total_abs_error / Decimal(str(bin_count))
    return avg_calibration_error


def grid_search() -> List[Dict]:
    """
    Test all combinations of home advantage and K-factor.
    
    Returns:
        List of results sorted by calibration error (best first)
        Each result: {
            'home_adv': value,
            'k_factor': value,
            'calibration_error': value,
            'num_predictions': value
        }
    """
    # Parameter ranges to test
    home_adv_values = [
        Decimal("20"),
        Decimal("30"),
        Decimal("40"),  # Current value
        Decimal("50"),
        Decimal("60")
    ]
    
    k_factor_values = [
        Decimal("5"),
        Decimal("10"),  # Current value
        Decimal("15"),
        Decimal("20")
    ]
    
    results = []
    total_experiments = len(home_adv_values) * len(k_factor_values)
    experiment_num = 0
    
    log.info("=" * 80)
    log.info("CALIBRATION PARAMETER TUNING - GRID SEARCH")
    log.info("=" * 80)
    log.info(f"Testing {len(home_adv_values)} home advantage values")
    log.info(f"Testing {len(k_factor_values)} K-factor values")
    log.info(f"Total experiments: {total_experiments}")
    log.info("=" * 80)
    log.info("")
    
    # Test every combination
    for home_adv in home_adv_values:
        for k_factor in k_factor_values:
            experiment_num += 1
            
            log.info(f"Experiment {experiment_num}/{total_experiments}: "
                     f"Home Adv={float(home_adv):.0f}, K={float(k_factor):.0f}")
            
            # Run replay with those parameters
            predictions = replay_with_params(
                home_advantage=home_adv,
                k_factor=k_factor
            )
            
            # Evaluate calibration
            calibration_error = evaluate_calibration(predictions)
            
            # Store result
            result = {
                'home_adv': float(home_adv),
                'k_factor': float(k_factor),
                'calibration_error': float(calibration_error),
                'num_predictions': len(predictions)
            }
            results.append(result)
            
            log.info(f"   -> Calibration Error: {float(calibration_error)*100:.2f}%")
            log.info("")
            
    # Sort by calibration error (best first)
    results.sort(key=lambda x: x['calibration_error'])
    
    return results


def print_results(results: List[Dict]):
    """
    Display grid search results in a formatted table.
    
    Shows all parameter combinations ranked by calibration error.
    Highlights best configuration and current configuration.
    """
    log.info("=" * 80)
    log.info("GRID SEARCH RESULTS")
    log.info("=" * 80)
    log.info("")
    
    # Table header
    log.info(f"{'Rank':<6} {'Home Adv':<12} {'K-Factor':<12} {'Cal Error':<14} {'Games':<8} {'Notes':<20}")
    log.info("-" * 80)
    
    # Current parameters for comparison
    current_home_adv = 40.0
    current_k_factor = 10.0
    
    for i, result in enumerate(results, 1):
        home_adv = result['home_adv']
        k_factor = result['k_factor']
        cal_error = result['calibration_error']
        num_games = result['num_predictions']
        
        # Mark current and best
        notes = ""
        if i == 1:
            notes = "** BEST **"
        if home_adv == current_home_adv and k_factor == current_k_factor:
            notes = "(current)"
        
        log.info(f"{i:<6} {home_adv:<12.0f} {k_factor:<12.0f} {cal_error*100:<13.2f}% {num_games:<8} {notes:<20}")
    
    log.info("")
    log.info("=" * 80)
    
    # Summary
    best = results[0]
    current = next((r for r in results if r['home_adv'] == current_home_adv and r['k_factor'] == current_k_factor), None)
    
    log.info("SUMMARY")
    log.info("-" * 80)
    log.info(f"Best Configuration:")
    log.info(f"  Home Advantage: {best['home_adv']:.0f} ELO points")
    log.info(f"  K-Factor: {best['k_factor']:.0f}")
    log.info(f"  Calibration Error: {best['calibration_error']*100:.2f}%")
    log.info("")
    
    if current:
        log.info(f"Current Configuration:")
        log.info(f"  Home Advantage: {current['home_adv']:.0f} ELO points")
        log.info(f"  K-Factor: {current['k_factor']:.0f}")
        log.info(f"  Calibration Error: {current['calibration_error']*100:.2f}%")
        log.info("")
        
        improvement = ((current['calibration_error'] - best['calibration_error']) / current['calibration_error']) * 100
        log.info(f"Potential Improvement: {improvement:.1f}% reduction in calibration error")
        
    log.info("=" * 80)
    

def main():
    """
    Run calibration parameter tuning.
    """
    log.info("")
    log.info("Starting calibration parameter tuning...")
    log.info("")
    
    # Run grid search
    results = grid_search()
    
    # Display results
    print_results(results)
    
    log.info("")
    log.info("Tuning complete!")
    log.info("")


if __name__ == "__main__":
    main()