# pipelines/analysis/variance_analysis.py
"""
Variance Analysis - Determine if performance is bad luck or bad strategy.

Statistical Framework:
- Uses binomial distribution to model bet outcomes
- Calculates z-scores to measure deviation from expected
- Provides actionable recommendations based on statistical significance
"""
import math
from decimal import Decimal
from pipelines.config import DATABASE_URL
from pipelines.common.db import connect
from pipelines.common.logging_setup import setup as setup_logging

setup_logging("INFO")

def calculate_z_score(actual_rate, expected_rate, n):
    """
    Calculate z-score (standard deviations from expected).
    
    Args:
        actual_rate: Observed win rate (e.g., 0.25 for 25%)
        expected_rate: Model predicted win rate (e.g., 0.55 for 55%)
        n: Number of bets
    
    Returns:
        z_score: How many standard deviations from expected
    """
    if expected_rate <= 0 or expected_rate >= 1 or n < 2:
        return 0
    
    # Binomial standard deviation: sqrt(p * (1-p) / n)
    std_dev = math.sqrt(expected_rate * (1 - expected_rate) / n)
    
    if std_dev == 0:
        return 0
    
    # Z-score = (observed - expected) / std_dev
    z_score = (actual_rate - expected_rate) / std_dev
    
    return z_score


def interpret_z_score(z_score, n):
    """
    Interpret z-score and provide recommendation.
    
    Statistical thresholds:
    - |z| < 1.0: Within 1 std dev (68% of outcomes) - Normal
    - |z| < 2.0: Within 2 std dev (95% of outcomes) - Concerning
    - |z| >= 2.0: Beyond 2 std dev (5% of outcomes) - Significant
    """
    abs_z = abs(z_score)
    
    # Rough estimate: need ~100 bets for good confidence
    required_sample = 100
    
    if abs_z < 1.0:
        verdict = "✅ WITHIN NORMAL VARIANCE"
        advice = "Continue betting, this is expected statistical noise"
    elif abs_z < 2.0:
        verdict = "⚠️  CONCERNING BUT POSSIBLE"
        advice = f"Reduce Kelly multiplier to 0.25x, need {max(0, required_sample - n)} more bets to judge definitively"
    else:
        verdict = "❌ STATISTICALLY SIGNIFICANT UNDERPERFORMANCE"
        advice = "Very unlikely to be random - disable strategy and investigate model"
    
    return verdict, advice


def analyze_variance():
    """Main variance analysis on current live bets."""
    
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # Get settled bets grouped by strategy
            cur.execute("""
                SELECT
                    bs.strategy_name,
                    COUNT(*) as total_bets,
                    SUM(CASE WHEN b.bet_status = 'won' THEN 1 ELSE 0 END) as wins,
                    AVG(b.model_prob) as avg_model_prob,
                    SUM(b.stake) as total_staked,
                    SUM(b.profit_loss) as total_profit
                FROM bet_log b
                JOIN betting_strategies bs ON b.strategy_id = bs.strategy_id
                WHERE b.bet_status IN ('won', 'lost', 'push')
                GROUP BY bs.strategy_name
                HAVING COUNT(*) > 0
                ORDER BY COUNT(*) DESC
            """)
            
            results = cur.fetchall()
            
            if not results:
                print("No settled bets found. Place some bets first!")
                return
            
            print("=" * 80)
            print("VARIANCE ANALYSIS - Current Live Bets")
            print("=" * 80)
            print()
            print("This analysis determines if your losses are bad luck or bad strategy.")
            print("Uses z-scores to measure how far from expected you are.")
            print()
            
            for row in results:
                name, n, wins, exp_win_rate, staked, profit = row
                
                # Skip if too few bets
                if n < 2:
                    print(f"{name}: Only {n} bet(s) - need at least 2 for analysis")
                    print()
                    continue
                    
                # Calculate metrics
                actual_win_rate = wins / n
                expected_win_rate = float(exp_win_rate)
                roi = (profit / staked * 100) if staked > 0 else 0
                
                # Calculate z-score
                z_score = calculate_z_score(actual_win_rate, expected_win_rate, n)
                
                # Get verdict and advice
                verdict, advice = interpret_z_score(z_score, n)
                
                # Display results
                print(f"{name}:")
                print(f"  Sample Size: {n} bets")
                print(f"  Win Rate: {actual_win_rate:.1%} | Expected: {expected_win_rate:.1%} | Gap: {(actual_win_rate - expected_win_rate):.1%}")
                print(f"  ROI: {roi:+.1f}% | Profit: ${profit:+.2f}")
                print(f"  Z-Score: {z_score:+.2f} standard deviations from expected")
                print(f"  Statistical Verdict: {verdict}")
                print(f"  Recommendation: {advice}")
                print()
                
            # Overall summary
            total_bets = sum(row[1] for row in results)
            total_wins = sum(row[2] for row in results)
            overall_staked = sum(row[4] for row in results)
            overall_profit = sum(row[5] for row in results)
            
            if total_bets > 0:
                overall_win_rate = total_wins / total_bets
                overall_roi = (overall_profit / overall_staked * 100) if overall_staked > 0 else 0
                
                print("=" * 80)
                print("OVERALL SYSTEM")
                print("=" * 80)
                print(f"Total Bets: {total_bets}")
                print(f"Win Rate: {overall_win_rate:.1%}")
                print(f"ROI: {overall_roi:+.1f}%")
                print(f"Profit/Loss: ${overall_profit:+.2f}")
                print()
                print(f"Sample Size Status: {total_bets}/100 bets (need ~100 for statistical confidence)")
                print("=" * 80)
                
if __name__ == "__main__":
    analyze_variance()
