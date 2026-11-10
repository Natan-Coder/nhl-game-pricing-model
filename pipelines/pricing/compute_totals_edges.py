# pipelines/pricing/compute_totals_edges.py
from dotenv import load_dotenv
import psycopg
import os
from scipy.stats import norm
from datetime import datetime
import logging

from pipelines.common.logging_setup import setup as setup_logging


setup_logging("INFO")
log = logging.getLogger(__name__)

# Setup
load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

def get_totals_std_dev() -> float:
    """
    Calculate std dev of NHL totals from recent season.
    
    Why: Measures how much game totals vary around the average
    Returns: Float like 2.2
    
    SQL: SELECT STDDEV(home_goals + away_goals) FROM game_results WHERE game_date >= '2025-10-01'
    """
    conn = psycopg.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("""
            SELECT STDDEV(home_goals + away_goals) as league_std_dev_total
            FROM game_results
            WHERE game_date >= '2025-10-01'
        """)
    result = cur.fetchone()
    conn.close()
    return float(result[0]) if result[0] else 2.2  # Default if no data


def calculate_over_probability(predicted_total: float, line_value: float, std_dev: float) -> float:
    """
    Use Normal distribution to find P(actual_total > line).
    
    Args:
        predicted_total: Your prediction (e.g., 6.71)
        line_value: Bookmaker line (e.g., 6.5)
        std_dev: Standard deviation (e.g., 2.2)
    
    Why: scipy.stats.norm.sf() gives "survival function" = P(X > value)
    
    Example:
        from scipy.stats import norm
        # sf = survival function = 1 - CDF
        over_prob = norm.sf(line_value, loc=predicted_total, scale=std_dev)
        return over_prob
    """
    over_prob = norm.sf(line_value, loc=predicted_total, scale=std_dev)
    return over_prob


def calculate_under_probability(over_prob: float) -> float:
    """
    Why: P(under) + P(over) = 1.0 (ignoring pushes on whole numbers)
    """
    return 1.0 - over_prob


def american_to_decimal(american_odds: int) -> float:
    """
    Convert American odds to decimal payout for edge calculation.
    
    Why: Need consistent format for math
    
    Examples:
        +110 → 1.10 (win $110 on $100 bet)
        -110 → 0.9091 (win $100 on $110 bet)
    
    Formula:
        if odds > 0: return odds / 100
        else: return 100 / abs(odds)
    """
    if american_odds > 0:
        return american_odds / 100
    else:
        return 100 / abs(american_odds)
    
    
def calculate_edge(probability: float, american_odds: int) -> float:
    """
    Calculate expected value as a percentage.
    
    Why: Positive edge = profitable bet long-term
    
    Formula:
        payout = american_to_decimal(american_odds)
        edge = (probability × payout) - ((1 - probability) × 1.0)
    
    Example: 55% prob, +110 odds
        edge = (0.55 × 1.10) - (0.45 × 1.0) = 0.155 = +15.5%
    """
    payout = american_to_decimal(american_odds)
    edge = (probability * payout) - ((1 - probability) * 1.0)
    return edge


def main():
    """
    Compute over/under edges for all games with predictions and odds.
    
    Steps:
    1. Get std_dev from historical data
    2. Query games with predicted_total and totals odds
    3. For each game + book combination:
        - Get over line and over odds
        - Get under odds (same line, different outcome)
        - Calculate over_prob
        - Calculate under_prob
        - Calculate over_edge
        - Calculate under_edge
        - Save to game_edges table
    
    Query structure:
        SELECT
            gp.game_id,
            gp.predicted_total,
            oq.book,
            oq.line_number / 100.0 as line_value,
            over_odds.american_odds as over_odds,
            under_odds.american_odds as under_odds
        FROM game_pricing gp
        JOIN game_features gf ON gp.game_id = gf.game_id
        JOIN odds_quotes over_odds ON gp.game_id = over_odds.game_id
            AND over_odds.market = 'total'
            AND over_odds.outcome = 'over'
        JOIN odds_quotes under_odds ON gp.game_id = under_odds.game_id
            AND under_odds.market = 'total'
            AND under_odds.outcome = 'under'
            AND under_odds.book = over_odds.book
            AND under_odds.line_number = over_odds.line_number
        WHERE gp.predicted_total IS NOT NULL
          AND gf.game_date >= CURRENT_DATE
    
    Note: You'll need to INSERT or UPDATE game_edges table
    Columns: game_id, book, market='total', line_number, outcome='over'/'under',
             edge_percentage, win_probability, captured_at
    """
    # Get std dev
    std_dev = get_totals_std_dev()
    print(f"Using std dev: {std_dev:.2f}")
    
    # Connect to database
    conn = psycopg.connect(DATABASE_URL)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT gp.game_id, gp.predicted_total, over_odds.book
               ,over_odds.line_number / 100.0 as line_value
               ,over_odds.american_odds as over_odds
               ,under_odds.american_odds as under_odds
        FROM game_pricing gp
        JOIN game_features gf ON gp.game_id = gf.game_id
        JOIN odds_quotes over_odds ON gp.game_id = over_odds.game_id
            AND over_odds.market = 'total'
            AND over_odds.outcome = 'over'
        JOIN odds_quotes under_odds ON gp.game_id = under_odds.game_id
            AND under_odds.market = 'total'
            AND under_odds.outcome = 'under'
            AND under_odds.book = over_odds.book
            AND under_odds.line_number = over_odds.line_number
        WHERE gp.predicted_total IS NOT NULL
          AND gf.game_date >= CURRENT_DATE - INTERVAL '1 day'
    """)
    
    games = cur.fetchall()
    print(f"Computing edges for {len(games)} game/book combinations...")
    
    # Loop through results
    for game_id, predicted_total, book, line_value, over_odds, under_odds in games:
        # Convert decimals to floats
        predicted_total = float(predicted_total)
        line_value = float(line_value)
        
        # Calculate probabilities
        over_prob = calculate_over_probability(predicted_total, line_value, std_dev)
        under_prob = calculate_under_probability(over_prob)
        
        # Calculate edges
        over_edge = calculate_edge(over_prob, over_odds)
        under_edge = calculate_edge(under_prob, under_odds)
        
        # Debug
        print(f"Game {game_id} ({book}): Line {line_value:.1f} | "
              f"Over {over_prob:.1%} edge={over_edge:+.2%} @ {over_odds:+} | "
              f"Under {under_prob:.1%} edge={under_edge:+.2%} @ {under_odds:+}")
        
        # Get current timestamp (rounded to minute for unique constraint)
        now = datetime.now()
        computed_minute = now.replace(second=0, microsecond=0)
        
        # Insert OVER edge into edges table
        cur.execute("""
            INSERT INTO edges (
                game_id, book, market, outcome, american_odds, line_number,
                implied_prob, model_prob, edge, kelly_fraction, bankroll, suggested_stake,
                computed_at, computed_minute_utc
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (game_id, book, market, outcome, american_odds, line_number, computed_minute_utc)
            DO UPDATE SET
                model_prob = EXCLUDED.model_prob,
                edge = EXCLUDED.edge,
                computed_at = EXCLUDED.computed_at
        """, (
            game_id, book, 'total', 'over', over_odds, int(line_value * 100)
            ,0.0  # implied_prob (placeholder)
            ,over_prob  # model_prob
            ,over_edge  # edge
            ,0.0  # kelly_fraction (placeholder)
            ,0.0  # bankroll (placeholder)
            ,0.0  # suggested_stake (placeholder)
            ,now, computed_minute
        ))
        
        # Insert UNDER edge into edges table
        cur.execute("""
            INSERT INTO edges (
                game_id, book, market, outcome, american_odds, line_number,
                implied_prob, model_prob, edge, kelly_fraction, bankroll, suggested_stake,
                computed_at, computed_minute_utc
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (game_id, book, market, outcome, american_odds, line_number, computed_minute_utc)
            DO UPDATE SET
                model_prob = EXCLUDED.model_prob,
                edge = EXCLUDED.edge,
                computed_at = EXCLUDED.computed_at
        """, (
            game_id, book, 'total', 'under', under_odds, int(line_value * 100)
            ,0.0  # implied_prob (placeholder)
            ,under_prob  # model_prob
            ,under_edge  # edge
            ,0.0  # kelly_fraction (placeholder)
            ,0.0  # bankroll (placeholder)
            ,0.0  # suggested_stake (placeholder)
            ,now, computed_minute
        ))
        
    # Commit and close
    conn.commit()
    conn.close()
    print("Done!")

if __name__ == "__main__":
    main()

    
    
    
    