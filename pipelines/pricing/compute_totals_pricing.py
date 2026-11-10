# pipelines/pricing/compute_totals_pricing.py
"""
Compute predicted totals (total goals) for upcoming games.

Approach:
1. Calculate league average total goals
2. For each team, calculate offensive/defensive ratings from recent games
3. Predict total = f(home_offense, away_offense, home_defense, away_defense)
4. Save to game_pricing.predicted_total
"""

from dotenv import load_dotenv
import psycopg
import os
from typing import Dict, Tuple

# Setup
load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

def get_league_average_total() -> float:
    """
    Calculate league average total goals from recent season.
    
    Why: Scoring rates change over time, use recent data
    Returns: Float like 6.04
    """
    conn = psycopg.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("""
        SELECT AVG(home_goals + away_goals) as league_avg_total
        FROM game_results
        WHERE game_date >= '2025-10-01'
    """)
    result = cur.fetchone()
    conn.close()
    return float(result[0]) if result[0] else 6.0  # Default if no data

def get_team_ratings(team: str, as_of_date: str) -> Tuple[float, float]:
    """
    Calculate team's offensive and defensive ratings.
    
    Args:
        team: Team identifier
        as_of_date: Don't use data after this date (avoid lookahead bias)
        
    Why: Need to separate offense (scoring) from defense (preventing)
    Returns: (offensive_rating, defensive_rating)
    """
    conn = psycopg.connect(DATABASE_URL)
    cur = conn.cursor()
    
    # Get last 20 games for this team (home + away games combined)
    # Offensive rating = goals scored
    # Defensive rating = goals allowed
    
    # Query for home games
    cur.execute("""
        SELECT AVG(goals_scored), AVG(goals_allowed)
        FROM (
            SELECT home_goals as goals_scored, away_goals as goals_allowed
            FROM game_results
            WHERE home_team = %s AND game_date < %s
            ORDER BY game_date DESC
            LIMIT 20
        ) recent_games
    """, (team, as_of_date))
    
    home_games = cur.fetchone()
    
    # Query for away games
    cur.execute("""
        SELECT AVG(goals_scored), AVG(goals_allowed)
        FROM (
            SELECT away_goals as goals_scored, home_goals as goals_allowed
            FROM game_results
            WHERE away_team = %s AND game_date < %s
            ORDER BY game_date DESC
            LIMIT 20
        ) recent_games
    """, (team, as_of_date))
    
    away_games = cur.fetchone()
    
    # Combine home & away stats
    if home_games[0] and away_games[0]:
        # Average of home and away offensive
        offensive = float((home_games[0] + away_games[0]) / 2)
        # Average of home and away defensive
        defensive = float((home_games[1] + away_games[1]) / 2)
    else:
        # Fallback to league average if not enough data
        offensive = 3.0  # Approximate NHL average
        defensive = 3.0
        
    conn.close()
    return offensive, defensive

def predict_game_total(home_team: str, away_team: str, game_date: str) -> float:
    """Predict total goals for a specific game."""
    # Get ratings
    home_off, home_def = get_team_ratings(home_team, game_date)
    away_off, away_def = get_team_ratings(away_team, game_date)
    
    # Predict how many goals each team will score
    # Home team scores against away defense
    home_expected = (home_off + away_def) / 2
    
    # Away team scored against home defense
    away_expected = (away_off + home_def) / 2
    
    # Add home ice advantage
    home_expected += 0.1
    
    predicted_total = home_expected + away_expected
    
    return predicted_total

def main():
    """Compute totals for all games needing predictions."""
    conn = psycopg.connect(DATABASE_URL)
    cur = conn.cursor()
    
    # Find games that need predictions
    # Option 1: All games in game_features without predicted_total
    # Option 2: Specific date range
    
    cur.execute("""
        SELECT gp.game_id, gf.home_team, gf.away_team, gf.game_date
        FROM game_pricing gp
        LEFT JOIN game_features gf ON gp.game_id = gf.game_id
        WHERE gf.game_date >= CURRENT_DATE
        ORDER BY gf.game_date
    """)
    
    games = cur.fetchall()
    print(f"Predicting totals for {len(games)} games...")
    
    for game_id, home_team, away_team, game_date in games:
        # Predict total
        predicted_total = predict_game_total(home_team, away_team, str(game_date))
        
        # Save to database
        cur.execute("""
            UPDATE game_pricing
            SET predicted_total = %s
            WHERE game_id = %s
        """, (predicted_total, game_id))
        
        print(f"Game {game_id}: Predicted {predicted_total:.2f} goals")

    conn.commit()
    conn.close()
    print("Done!")

if __name__ == "__main__":
    main()