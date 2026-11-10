"""
Evaluate live model performance vs backtest baseline.

Measures:
- Overall accuracy
- Rolling accuracy (7, 14, 30 days)
- Calibration error
- Comparison to backtest (56.74% baseline)
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Tuple
import psycopg

from pipelines.config import DATABASE_URL
from pipelines.common.logging_setup import setup as setup_logging

setup_logging("INFO")
log = logging.getLogger(__name__)

# Backtest baseline from your validation
BACKTEST_ACCURACY = Decimal("0.5674")  # 56.74%
BACKTEST_CALIBRATION_ERROR = Decimal("0.0611")  # 6.11%

# Alert thresholds
ACCURACY_WARNING_THRESHOLD = Decimal("0.54")  # Warn if < 54%
ACCURACY_CRITICAL_THRESHOLD = Decimal("0.51")  # Critical if < 51%

def load_completed_predictions(conn) -> List[Dict]:
    """
    Load all predictions where the game has finished.
    
    Returns list of dicts with prediction data.
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                lp.prediction_id,
                lp.game_id,
                lp.predicted_at,
                lp.home_elo,
                lp.away_elo,
                lp.predicted_home_win_prob,
                lp.actual_home_won,
                lp.prediction_correct,
                gr.game_date,
                gr.home_team,
                gr.away_team
            FROM live_predictions lp
            INNER JOIN game_results gr ON gr.game_id = lp.game_id
            WHERE lp.actual_home_won IS NOT NULL
            ORDER BY gr.game_date DESC
        """)
        
        rows = cur.fetchall()
        
    predictions = []
    for row in rows:
        predictions.append({
            "prediction_id": row[0],
            "game_id": row[1],
            "predicted_at": row[2],
            "home_elo": row[3],
            "away_elo": row[4],
            "predicted_home_win_prob": row[5],
            "actual_home_won": row[6],
            "prediction_correct": row[7],
            "game_date": row[8],
            "home_team": row[9],
            "away_team": row[10],
        })
        
    return predictions


def calculate_accuracy(predictions: List[Dict]) -> Tuple[Decimal, int, int]:
    """
    Calculate accuracy from predictions.
    
    Returns: (accuracy, correct_count, total_count)
    """
    if not predictions:
        return Decimal("0"), 0, 0
    
    correct = sum(1 for p in predictions if p["prediction_correct"])
    total = len(predictions)
    accuracy = Decimal(str(correct)) / Decimal(str(total))
    
    return accuracy, correct, total


def calculate_calibration_error(predictions: List[Dict]) -> Decimal:
    """
    Calculate calibration error (simplified version).
    
    Groups predictions into bins and measures average deviation.
    """
    if not predictions:
        return Decimal("0")
    
    bins = {}
    bin_width = Decimal("0.05")
    
    for pred in predictions:
        prob = Decimal(str(pred["predicted_home_win_prob"]))
        actual = 1 if pred["actual_home_won"] else 0
        
        # Determine bin
        bin_num = int(prob / bin_width)
        bin_key = bin_num * bin_width
        
        if bin_key not in bins:
            bins[bin_key] = {"predicted": [], "actual": []}
            
        bins[bin_key]["predicted"].append(prob)
        bins[bin_key]["actual"].append(actual)
        
    # Calculate average error across bins
    errors = []
    for bin_key, data in bins.items():
        if len(data["actual"]) < 5:  # Skip bins with too few samples
            continue
            
        avg_predicted = sum(data["predicted"]) / len(data["predicted"])
        avg_actual = Decimal(str(sum(data["actual"]))) / Decimal(str(len(data["actual"])))
        
        error = abs(avg_predicted - avg_actual)
        errors.append(error)
        
    if not errors:
        return Decimal("0")
    
    calibration_error = sum(errors) / len(errors)
    return calibration_error

def calculate_team_performance(predictions: List[Dict], team_name: str) -> Dict:
    """
    Calculate performance metrics for a specific team.
    
    Returns breakdown of accuracy by:
    - Overall
    - Home vs Away
    - Favorite vs Underdog
    """
    # Find all games involving this team
    team_predictions = []
    
    for pred in predictions:
        if pred["home_team"] == team_name or pred["away_team"] == team_name:
            is_home = pred["home_team"] == team_name
            home_prob = Decimal(str(pred["predicted_home_win_prob"]))
            
            # Determine if team was favored
            if is_home:
                is_favorite = home_prob > Decimal("0.5")
            else:
                is_favorite = home_prob < Decimal("0.5")
            
            team_predictions.append({
                **pred,
                "team_was_home": is_home,
                "team_was_favorite": is_favorite
            })
            
    if not team_predictions:
        return None  # Team not found
    
    # Overall stats
    overall_acc, overall_correct, overall_total = calculate_accuracy(team_predictions)
    
    # Home/Away splits
    home_preds = [p for p in team_predictions if p["team_was_home"]]
    away_preds = [p for p in team_predictions if not p["team_was_home"]]
    
    home_acc, home_correct, home_total = calculate_accuracy(home_preds)
    away_acc, away_correct, away_total = calculate_accuracy(away_preds)
    
    # Favorite/Underdog splits
    fav_preds = [p for p in team_predictions if p["team_was_favorite"]]
    dog_preds = [p for p in team_predictions if not p["team_was_favorite"]]
    
    fav_acc, fav_correct, fav_total = calculate_accuracy(fav_preds)
    dog_acc, dog_correct, dog_total = calculate_accuracy(dog_preds)
    
    return {
        "team_name": team_name,
        "overall": {
            "accuracy": float(overall_acc),
            "correct": overall_correct,
            "total": overall_total
            },
        "home": {
            "accuracy": float(home_acc),
            "correct": home_correct,
            "total": home_total
            },
        "away": {
            "accuracy": float(away_acc),
            "correct": away_correct,
            "total": away_total
            },
        "as_favorite": {
            "accuracy": float(fav_acc),
            "correct": fav_correct,
            "total": fav_total
            },
        "as_underdog": {
            "accuracy": float(dog_acc),
            "correct": dog_correct,
            "total": dog_total
        }
    }


def get_unique_teams(predictions: List[Dict]) -> List[str]:
    """Get list of unique team names from predictions."""
    teams = set()
    for pred in predictions:
        teams.add(pred["home_team"])
        teams.add(pred["away_team"])
    return sorted(list(teams))


def filter_by_date_range(predictions: List[Dict], days: int) -> List[Dict]:
    """Filter predictions to last N days."""
    cutoff = datetime.now().date() - timedelta(days=days)
    return [p for p in predictions if p["game_date"] >= cutoff]


def print_performance_report(predictions: List[Dict]):
    """Print formatted performance report."""
    
    if not predictions:
        log.info("=" * 80)
        log.info("LIVE MODEL PERFORMANCE")
        log.info("=" * 80)
        log.info("No completed predictions yet.")
        log.info("=" * 80)
        return
    
    # Overall stats
    overall_acc, overall_correct, overall_total = calculate_accuracy(predictions)
    overall_calib = calculate_calibration_error(predictions)
    
    # Time windows
    last_7_preds = filter_by_date_range(predictions, 7)
    last_14_preds = filter_by_date_range(predictions, 14)
    last_30_preds = filter_by_date_range(predictions, 30)
    
    acc_7, correct_7, total_7 = calculate_accuracy(last_7_preds)
    acc_14, correct_14, total_14 = calculate_accuracy(last_14_preds)
    acc_30, correct_30, total_30 = calculate_accuracy(last_30_preds)
    
    # Print report
    log.info("=" * 80)
    log.info("LIVE MODEL PERFORMANCE")
    log.info("=" * 80)
    log.info("")
    
    log.info("BASELINE (from backtest):")
    log.info(f"  Accuracy:          {float(BACKTEST_ACCURACY)*100:.2f}%")
    log.info(f"  Calibration Error: {float(BACKTEST_CALIBRATION_ERROR)*100:.2f}%")
    log.info("")
    
    log.info("LIVE PERFORMANCE:")
    log.info(f"  All-Time:  {float(overall_acc)*100:.2f}% ({overall_correct}/{overall_total} games)")
    log.info(f"  Last 30d:  {float(acc_30)*100:.2f}% ({correct_30}/{total_30} games)")
    log.info(f"  Last 14d:  {float(acc_14)*100:.2f}% ({correct_14}/{total_14} games)")
    log.info(f"  Last 7d:   {float(acc_7)*100:.2f}% ({correct_7}/{total_7} games)")
    log.info("")
    
    log.info(f"CALIBRATION ERROR: {float(overall_calib)*100:.2f}%")
    log.info("")
    
    # Compare to baseline
    acc_diff = overall_acc - BACKTEST_ACCURACY
    calib_diff = overall_calib - BACKTEST_CALIBRATION_ERROR
    
    log.info("COMPARISON TO BASELINE:")
    log.info(f"  Accuracy:          {'+' if acc_diff >= 0 else ''}{float(acc_diff)*100:.2f}%")
    log.info(f"  Calibration Error: {'+' if calib_diff >= 0 else ''}{float(calib_diff)*100:.2f}%")
    log.info("")
    
    # Alerts
    if overall_acc < ACCURACY_CRITICAL_THRESHOLD:
        log.info("*** CRITICAL: Accuracy below 51% threshold! ***")
        log.info("")
    elif overall_acc < ACCURACY_WARNING_THRESHOLD:
        log.info("*** WARNING: Accuracy below 54% threshold ***")
        log.info("")
    
    log.info("=" * 80)


def print_team_performance_summary(predictions: List[Dict]):
    """Print top and bottom performing teams."""
    
    if not predictions:
        return
    
    log.info("")
    log.info("=" * 80)
    log.info("TEAM PERFORMANCE BREAKDOWN")
    log.info("=" * 80)
    log.info("")
    
    # Get all teams and calculate their performance
    teams = get_unique_teams(predictions)
    team_stats = []
    
    for team in teams:
        perf = calculate_team_performance(predictions, team)
        if perf and perf["overall"]["total"] >= 5:  # At least 5 games
            team_stats.append(perf)
    
    if not team_stats:
        log.info("Not enough team data to analyze (need 5+ games per team)")
        log.info("=" * 80)
        return
        
    # Sort by overall accuracy
    team_stats.sort(key=lambda x: x["overall"]["accuracy"], reverse=True)
    
    # Top 3 performers
    log.info("TOP 3 PERFORMING TEAMS:")
    for i, team in enumerate(team_stats[:3], 1):
        log.info(f"{i}. {team['team_name']}")
        log.info(f"   Overall: {team['overall']['accuracy']*100:.2f}% ({team['overall']['correct']}/{team['overall']['total']} games)")
        log.info(f"   Home:    {team['home']['accuracy']*100:.2f}% ({team['home']['correct']}/{team['home']['total']})")
        log.info(f"   Away:    {team['away']['accuracy']*100:.2f}% ({team['away']['correct']}/{team['away']['total']})")
        log.info("")
        
    # Bottom 3 performers
    log.info("BOTTOM 3 PERFORMING TEAMS:")
    for i, team in enumerate(team_stats[-3:], 1):
        log.info(f"{i}. {team['team_name']}")
        log.info(f"   Overall: {team['overall']['accuracy']*100:.2f}% ({team['overall']['correct']}/{team['overall']['total']} games)")
        log.info(f"   Home:    {team['home']['accuracy']*100:.2f}% ({team['home']['correct']}/{team['home']['total']})")
        log.info(f"   Away:    {team['away']['accuracy']*100:.2f}% ({team['away']['correct']}/{team['away']['total']})")
        log.info("")
    
    log.info("=" * 80)


if __name__ == "__main__":
    log.info("Starting live performance evaluation...")
    
    conn = None
    try:
        conn = psycopg.connect(DATABASE_URL)
        log.info("Connected to database")
        
        predictions = load_completed_predictions(conn)
        log.info(f"Loaded {len(predictions)} completed predictions")
        
        print_performance_report(predictions)
        print_team_performance_summary(predictions)
        
    except Exception as e:
        log.error(f"Error during evaluation: {e}", exc_info=True)
        raise
    finally:
        if conn:
            conn.close()
            log.info("Database connection closed")
    