# pipelines/analysis/backtest_elo.py
"""
 Backtest the Elo rating model against historical NHL game results.

 This script:
 1. Loads all historical game results from the database
 2. Simulates the Elo model forward in time
 3. Makes predictions BEFORE updating Elos (no look-ahead bias)
 4. Calculates accuracy metrics and calibration
 5. Identifies optimal Elo parameters
 """
from __future__ import annotations
import sys
import logging
from datetime import date
from decimal import Decimal, getcontext
from typing import List, Tuple
import psycopg

from pipelines.config import DATABASE_URL
from pipelines.common.db import connect, execute_one
from pipelines.common.logging_setup import setup as setup_logging

setup_logging("INFO")
log = logging.getLogger(__name__)
getcontext().prec = 28

# -------- Configurable Parameters --------
# These are the parameters we'll test/tune
K_FACTOR = Decimal("20")       # Update strength (higher = faster adaptation)
HOME_ICE = Decimal("30")       # Home ice advantage in Elo points
INITIAL_ELO = Decimal("1500")  # Starting Elo for all teams

# -------- Elo Calculation --------
def expected_win_prob(elo_a: Decimal, elo_b: Decimal) -> Decimal:
    """
    Calculate expected win probability for team A vs team B.
    Uses logistic function from Bradley-Terry model.
    """
    diff = (elo_a - elo_b) / Decimal("400")
    ten = Decimal("10") ** diff
    return ten / (Decimal("1") + ten)

def update_elo(
    winner_elo: Decimal,
    loser_elo: Decimal,
    k_factor: Decimal,
    winner_was_home: bool,
    home_ice_advantage: Decimal,
) -> Tuple[Decimal, Decimal]:
    """
    Update Elo ratings for winner and loser.
    Returns (new_winner_elo, new_loser_elo).
    """
    # Apply home ice to expected probability calculation
    if winner_was_home:
        expected = expected_win_prob(winner_elo + home_ice_advantage, loser_elo)
    else:
        expected = expected_win_prob(winner_elo, loser_elo + home_ice_advantage)
        
    # Winner gets (1 - expected), loser gets (0 - (1 - expected))
    winner_new = winner_elo + k_factor * (Decimal("1") - expected)
    loser_new = loser_elo + k_factor * (Decimal("0") - (Decimal("1") - expected))
    
    return winner_new, loser_new


# -------- Metrics Calculation --------
def calculate_log_loss(predictions: List[Tuple[Decimal, bool]]) -> float:
    """
    Calculate log loss (cross-entropy) for binary predictions.
    Lower is better. Random guessing = 0.693.
    
    predictions: List of (predicted_prob, actual_outcome) tuples
    """
    if not predictions:
        return float("inf")
    
    total = Decimal("0")
    for pred_prob, actual in predictions:
        # Clip probabilities to avoid log(0)
        p = max(min(pred_prob, Decimal("0.9999")), Decimal("0.0001"))
        
        if actual:  # Home team won
            total += -(Decimal("1") * p.ln())
        else:  # Away team won
            total += -(Decimal("1") - p).ln()
            
    return float(total / len(predictions))


def calculate_brier_score(predictions: List[Tuple[Decimal, bool]]) -> float:
    """
    Calculate Brier score (mean squared error of probabilities).
    Lower is better. Random guessing = 0.25.
    
    predictions: List of (predicted_prob, actual_outcome) tuples
    """
    if not predictions:
        return float("inf")
    
    total = Decimal("0")
    for pred_prob, actual in predictions:
        actual_val = Decimal("1") if actual else Decimal("0")
        total += (pred_prob - actual_val) ** 2
        
    return float(total / len(predictions))


def calculate_accuracy(predictions: List[Tuple[Decimal, bool]]) -> float:
    """
    Calculate simple accuracy (% of correct predictions).
    
    predictions: List of (predicted_prob, actual_outcome) tuples
    """
    if not predictions:
        return 0.0
    
    correct = sum(
        1 for pred_prob, actual in predictions
        if (pred_prob > Decimal("0.5")) == actual
    )
    
    return correct / len(predictions)


def calculate_calibration(
    predictions: List[Tuple[Decimal, bool]],
    num_bins: int = 10
) -> List[Tuple[float, float, int]]:
    """
    Calculate calibration curve by binning predictions.
    Returns list of (avg_predicted, avg_actual, count) for each bin.
  
    Well-calibrated model: avg_predicted ≈ avg_actual for all bins.
    """
    # Sort predictions into bins
    bins = [[] for _ in range(num_bins)]
    for pred_prob, actual in predictions:
        bin_idx = min(int(float(pred_prob) * num_bins), num_bins - 1)
        bins[bin_idx].append((pred_prob, actual))
        
    # Calculate average for each bin
    calibration = []
    for bin_predictions in bins:
        if not bin_predictions:
            continue
            
        avg_pred = sum(p for p, _ in bin_predictions) / len(bin_predictions)
        avg_actual = sum(1 for _, a in bin_predictions if a) / len(bin_predictions)
        count = len(bin_predictions)
        
        calibration.append((float(avg_pred), avg_actual, count))
        
    return calibration
    
    # -------- Main Backtest Logic --------
def run_backtest(
    k_factor: Decimal = K_FACTOR,
    home_ice: Decimal = HOME_ICE,
    initial_elo: Decimal = INITIAL_ELO,
    verbose: bool = True,
) -> dict:
    """
    Run backtest with specified parameters.
    Returns dict with metrics and predictions.
    """
    # Load historical game results (ordered by date)
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            execute_one(cur,"""
                SELECT game_id, game_date, home_team, away_team, home_goals, away_goals
                FROM game_results
                ORDER BY game_date, game_id
            """)
            games = cur.fetchall()
            
    if not games:
        log.error("No game results found in database")
        return {}
    
    log.info("Loaded %d historical games for backtesting", len(games))
    
    # Initialize Elo ratings
    elo_ratings = {}   # team_abbr -> current Elo
    predictions = []   # (predicted_home_win_prob, actual_home_won)
    
    # Simulate forward in time
    for game_id, game_date, home, away, home_goals, away_goals in games:
        # Get current Elos (default to initial if team not seen)
        home_elo = elo_ratings.get(home, initial_elo)
        away_elo = elo_ratings.get(away, initial_elo)
        
        # PREDICT BEFORE UPDATING (no look-ahead bias)
        pred_home_win_prob = expected_win_prob(home_elo + home_ice, away_elo)
        actual_home_won = home_goals > away_goals
        
        predictions.append((pred_home_win_prob, actual_home_won))
        
        # UPDATE ELOS AFTER PREDICTION
        if home_goals > away_goals:  # Home won
            home_elo, away_elo = update_elo(
                home_elo, away_elo, k_factor,
                winner_was_home=True, home_ice_advantage=home_ice
            )
        else:  # Away won
            away_elo, home_elo = update_elo(
                away_elo, home_elo, k_factor,
                winner_was_home=False, home_ice_advantage=home_ice
            )
            
        # Store updated Elos
        elo_ratings[home] = home_elo
        elo_ratings[away] = away_elo
        
    # Calculate metrics
    log_loss = calculate_log_loss(predictions)
    brier_score = calculate_brier_score(predictions)
    accuracy = calculate_accuracy(predictions)
    calibration = calculate_calibration(predictions)
    
    if verbose:
        log.info("")
        log.info("=" * 60)
        log.info("BACKTEST RESULTS")
        log.info("=" * 60)
        log.info("Parameters:")
        log.info("  K-factor: %s", k_factor)
        log.info("  Home ice advantage: %s Elo points", home_ice)
        log.info("  Initial Elo: %s", initial_elo)
        log.info("")
        log.info("Metrics:")
        log.info("  Games evaluated: %d", len(predictions))
        log.info("  Accuracy: %.2f%%", accuracy * 100)
        log.info("  Log Loss: %.4f (random = 0.693)", log_loss)
        log.info("  Brier Score: %.4f (random = 0.250)", brier_score)
        log.info("")
        log.info("Calibration (predicted vs actual win rate by decile):")
        log.info("  Bin  |  Predicted  |  Actual  |  Count")
        log.info("  " + "-" * 45)
        for i, (pred, actual, count) in enumerate(calibration):
            log.info("  %2d   |    %.3f    |  %.3f   |  %5d",
                     i+1, pred, actual, count)
        log.info("=" * 60)
        
        # Interpretation
        if log_loss < 0.693:
            log.info("✓ Model beats random guessing (log loss < 0.693)")
        else:
            log.warning("✗ Model no better than random guessing")
            
        if accuracy > 0.5:
            log.info("✓ Model accuracy better than coin flip")
        else:
            log.warning("✗ Model accuracy worse than coin flip")
            
        # Check calibration quality
        calibration_error = sum(
            abs(pred - actual) * count
            for pred, actual, count in calibration
        ) / len(predictions)
        log.info("Mean calibration error: %.4f", calibration_error)
        
        if calibration_error < 0.05:
            log.info("✓ Model is well calibrated")
        else:
            log.warning("⚠ Model may need calibration adjustment")
            
    return {
        "predictions": predictions,
        "elo_ratings": elo_ratings,
        "log_loss": log_loss,
        "brier_score": brier_score,
        "accuracy": accuracy,
        "calibration": calibration,
        "num_games": len(predictions),
    }
    
    
    # -------- Parameter Tuning --------
def grid_search_parameters():
    """
    Test multiple parameter combinations to find optimal settings.
    """
    log.info("Starting parameter grid search...")
    
    k_values = [Decimal(str(k)) for k in [10, 15, 20, 25, 30]]
    home_ice_values = [Decimal(str(h)) for h in [20, 30, 40,50]]
    
    best_log_loss = float("inf")
    best_params = None
    results = []
    
    total = len(k_values) * len(home_ice_values)
    current = 0
    
    for k in k_values:
        for home_ice in home_ice_values:
            current += 1
            log.info("Testing [%d/%d]: K=%s, HomeIce=%s",
                     current, total, k, home_ice)
            
            result = run_backtest(
                k_factor=k,
                home_ice=home_ice,
                initial_elo=INITIAL_ELO,
                verbose=False,
            )
            
            results.append({
                "k_factor": k,
                "home_ice": home_ice,
                "log_loss": result["log_loss"],
                "brier_score": result["brier_score"],
                "accuracy": result["accuracy"],
            })
            
            if result["log_loss"] < best_log_loss:
                best_log_loss = result["log_loss"]
                best_params = (k, home_ice)
                
    # Print results
    log.info("")
    log.info("=" * 60)
    log.info("GRID SEARCH RESULTS")
    log.info("=" * 60)
    log.info("K-Factor | HomeIce | LogLoss | Brier  | Accuracy")
    log.info("-" * 60)
    for r in sorted(results, key=lambda x: x["log_loss"]):
        log.info("   %5s |    %4s  | %.4f  | %.4f | %.2f%%",
                 r["k_factor"], r["home_ice"],
                 r["log_loss"], r["brier_score"], r["accuracy"] * 100)
    
    log.info("=" * 60)
    log.info("Best parameters: K=%s, HomeIce=%s (LogLoss=%.4f)",
             best_params[0], best_params[1], best_log_loss)
    log.info("=" * 60)
    
    return best_params, results
    
    # -------- Entry Point --------
def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Backtest the Elo rating model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--grid-search",
        action="store_true",
        help="Run grid search to find optimal parameters",
    )
    parser.add_argument(
        "--k-factor",
        type=float,
        default=float(K_FACTOR),
        help=f"K-factor for Elo updates (default: {K_FACTOR})",
    )
    parser.add_argument(
        "--home-ice",
        type=float,
        default=float(HOME_ICE),
        help=f"Home ice advantage in Elo points (default: {HOME_ICE})",
    )
    
    args = parser.parse_args()
    
    if args.grid_search:
        grid_search_parameters()
    else:
        run_backtest(
            k_factor=Decimal(str(args.k_factor)),
            home_ice=Decimal(str(args.home_ice)),
            initial_elo=INITIAL_ELO,
            verbose=True,
        )
        
if __name__ == "__main__":
    main()
