# pipelines/analysis/replay_elos.py
"""
ELO Replay Engine - Reconstruct historical ELO ratings

This script "replays" your ELO calculation system on historical data
to validate model accuracy. It answers: "If we had been using this
model during the 2023-24 season, how accurate would our predictions
have been?"

Process:
1. Start with all teams at 1500 ELO (or custom starting ratings)
2. Process games chronologically (day by day)
3. Before each game, calculate predicted win probability
4. After each game, update ELO ratings (just like live system)
5. Store ELO history and predictions for analysis

This lets us test model calibration, Brier score, and accuracy
without needing historical odds data.
"""

from __future__ import annotations
import logging
from datetime import datetime, date
from decimal import Decimal, getcontext
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

from pipelines.config import DATABASE_URL
from pipelines.common.db import connect, execute_one
from pipelines.common.logging_setup import setup as setup_logging
from pipelines.pricing.utils import get_recent_form, apply_form_adjustment, get_rest_adjustment, calculate_goalie_advantage

setup_logging("INFO")
getcontext().prec = 28
log = logging.getLogger(__name__)

# ============================================================
# ELO Configuration (matches your current system)
# ============================================================
K_FACTOR = Decimal("10")   # Update strength (from compute_team_elos.py)
HOME_ADV = Decimal("50")    # Home ice advantage (from compute_team_elos.py)
STARTING_ELO = Decimal("1500")  # Default ELO for new teams

# ============================================================
# Core ELO Functions (replicated from your system)
# ============================================================

def calculate_expected_win_prob(elo_a: Decimal, elo_b: Decimal) -> Decimal:
    """
    Calculate expected win probability using ELO difference.

    This is the Bradley-Terry model via ELO logistic formula.
    Same as _expected() in your compute_team_elos.py

    Args:
        elo_a: Team A's ELO rating
        elo_b: Team B's ELO rating

    Returns:
        Probability that Team A wins (0.0 to 1.0)

    Example:
        If Team A has ELO 1600 and Team B has 1500:
        - ELO diff = 100
        - Expected win prob ≈ 64%
    """
    diff = (elo_a - elo_b) / Decimal("400")
    ten_pow = Decimal("10") ** diff
    expected = ten_pow / (Decimal("1") + ten_pow)
    return expected


def update_elo_after_game(
    home_elo: Decimal,
    away_elo: Decimal,
    home_won: bool,
    k_factor: Decimal = K_FACTOR
) -> Tuple[Decimal, Decimal]:
    """
    Update both teams' ELO ratings after a game.

    This replicates the logic from your compute_team_elos.py

    Args:
        home_elo: Home team's ELO before game
        away_elo: Away team's ELO before game
        home_won: True if home team won, False if away won
        k_factor: Learning rate (default 10)

    Returns:
        (new_home_elo, new_away_elo)

    How It Works:
    1. Calculate expected outcome (with home ice advantage)
    2. Compare to actual outcome (1.0 if home won, 0.0 if away won)
    3. Adjust ELOs based on surprise factor
       - If favorite wins: small ELO change
       - If underdog wins: large ELO change
    """
    # Calculate expected with home ice advantage
    expected_home_win = calculate_expected_win_prob(home_elo + HOME_ADV, away_elo)
    
    # Actual outcome
    actual_home = Decimal("1.0") if home_won else Decimal("0.0")
    
    # Update home team ELO
    # If home won when expected to lose: big ELO boost
    # If home lost when expected to win: big ELO drop
    new_home_elo = home_elo + k_factor * (actual_home - expected_home_win)
    
    # Update away team ELO (mirror logic)
    expected_away_win = Decimal("1.0") - expected_home_win
    actual_away = Decimal("1.0") - actual_home
    new_away_elo = away_elo + k_factor * (actual_away - expected_away_win)
    
    return new_home_elo, new_away_elo


# ============================================================
# Replay Engine
# ============================================================

def initialize_teams(starting_elo: Decimal = STARTING_ELO) -> Dict[str, Decimal]:
    """
    Initialize all teams with starting ELO rating.

    In a real system, you might:
    - Start teams at different ELOs based on previous season
    - Apply regression to mean (bring all teams closer to 1500)

    For simplicity, we start everyone at 1500.

    Returns:
        Dictionary mapping team_code -> elo_rating
    """
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # Get all unique team codes from game results
            cur.execute("""
                SELECT DISTINCT home_team FROM game_results
                UNION
                SELECT DISTINCT away_team FROM game_results
            """)
            teams = [row[0] for row in cur.fetchall()]
    
    log.info(f"Initializing {len(teams)} teams at ELO {starting_elo}")
    
    return {team: starting_elo for team in teams}


def get_games_for_replay(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> List[Dict]:
    """
    Get all games in chronological order for replay.

    Args:
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)

    Returns:
        List of game dicts with:
        - game_id, game_date
        - home_team, away_team
        - home_goals, away_goals
        - home_won (bool)
    """
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # Build date filter
            where_clauses = []
            params = []
            
            if start_date:
                where_clauses.append("gr.game_date >= %s")
                params.append(start_date)
            if end_date:
                where_clauses.append("gr.game_date <= %s")
                params.append(end_date)
            
            where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
            
            # Get games ordered chronologically
            query = f"""
                SELECT gr.game_id, gr.game_date, gr.home_team, gr.away_team,
                       gr.home_goals, gr.away_goals,
                       gf.home_rest_days, gf.away_rest_days,
                       gf.home_goalie_sv_pct, gf.away_goalie_sv_pct
                FROM game_results gr
                LEFT JOIN game_features gf ON gr.game_id = gf.game_id
                {where_sql}
                ORDER BY gr.game_date, gr.game_id
            """
            
            cur.execute(query, params)
            rows = cur.fetchall()
            
            games = []
            for row in rows:
                games.append({
                    "game_id": row[0],
                    "game_date": row[1],
                    "home_team": row[2],
                    "away_team": row[3],
                    "home_goals": row[4],
                    "away_goals": row[5],
                    "home_won": row[4] > row[5],
                    "home_rest_days": row[6] if len(row) > 6 else None,
                    "away_rest_days": row[7] if len(row) > 7 else None,
                    "home_goalie_sv_pct": row[8] if len(row) > 8 else None,
                    "away_goalie_sv_pct": row[9] if len(row) > 9 else None
                })
            
            log.info(f"Loaded {len(games)} games for replay")
            return games


def replay_elos(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    save_history: bool = True
) -> Tuple[List[Dict], Dict[str, Decimal]]:
    """
    Main replay function - reconstruct historical ELOs and predictions.

    This is the core of the system. It processes games chronologically,
    calculating what your model would have predicted at each point in time.

    Args:
        start_date: Start date for replay
        end_date: End date for replay
        save_history: If True, save ELO snapshots to database

    Returns:
        (predictions, final_elos)
        - predictions: List of prediction dicts for each game
        - final_elos: Final ELO ratings after all games

    Prediction Dict Contains:
        - game_id, game_date
        - home_team, away_team
        - home_elo_before, away_elo_before (ELOs at time of game)
        - predicted_home_win_prob (model prediction)
        - actual_home_won (actual outcome)
        - prediction_correct (bool)
    """
    log.info("=" * 60)
    log.info("Starting ELO Replay")
    log.info("=" * 60)
    
    # Step 1: Initialize all teams
    team_elos = initialize_teams()
    games_played = defaultdict(int)  # Track how many games each team has played
    
    # Step 2: Get all games
    games = get_games_for_replay(start_date, end_date)
    
    if not games:
        log.warning("No games found in date range")
        return [], team_elos
    
    # Open database connection for form queries (reuse across all games)
    with connect(DATABASE_URL) as conn:
        # Step 3: Process each game
        predictions = []
        season = None  # Will be determined from first game
    
        for i, game in enumerate(games):
            game_id = game["game_id"]
            game_date = game["game_date"]
            home = game["home_team"]
            away = game["away_team"]
            home_won = game["home_won"]
        
            # Determine season (simple heuristic: Oct-Jun = same season)
            if season is None:
                year = game_date.year
                month = game_date.month
                if month >= 10:  # Oct - Dec
                    season = f"{year}-{str(year+1)[-2:]}"
                else:  # Jan-Jun
                    season = f"{year-1}-{str(year)[-2:]}"
            
            # Get current ELOs (before this game)
            home_elo = team_elos.get(home, STARTING_ELO)
            away_elo = team_elos.get(away, STARTING_ELO)
        
            # Save ELO snapshot BEFORE this game
            if save_history:
                save_elo_snapshot(game_id, game_date, team_elos, games_played, season)
            
            # Apply recent form adjustments
            home_form = get_recent_form(home, game_date, lookback_games=10, conn=conn)
            away_form = get_recent_form(away, game_date, lookback_games=10, conn=conn)
            home_elo_adjusted = apply_form_adjustment(home_elo, home_form)
            away_elo_adjusted = apply_form_adjustment(away_elo, away_form)
            
            # Apply rest day adjustments
            home_rest = game.get('home_rest_days')
            away_rest = game.get('away_rest_days')
            home_elo_adjusted += get_rest_adjustment(home_rest)
            away_elo_adjusted += get_rest_adjustment(away_rest)
            
            # Apply goalie advantage adjustment
            home_goalie_sv = game.get('home_goalie_sv_pct')
            away_goalie_sv = game.get('away_goalie_sv_pct')
            goalie_adjustment = calculate_goalie_advantage(home_goalie_sv, away_goalie_sv)
            home_elo_adjusted += goalie_adjustment
            
            # Calculate prediction (with home ice advantage)
            predicted_home_win_prob = calculate_expected_win_prob(
                home_elo_adjusted + HOME_ADV,
                away_elo_adjusted
            )
        
            # Record prediction
            prediction = {
                'game_id': game_id,
                'game_date': game_date,
                'home_team': home,
                'away_team': away,
                'home_elo_before': home_elo,
                'away_elo_before': away_elo,
                'predicted_home_win_prob': predicted_home_win_prob,
                'actual_home_won': home_won,
                'prediction_correct': (predicted_home_win_prob > 0.5) == home_won,
                'season': season
            }
            predictions.append(prediction)
        
            # Update ELOs based on actual result
            new_home_elo, new_away_elo = update_elo_after_game(
                home_elo,
                away_elo,
                home_won
            )
        
            team_elos[home] = new_home_elo
            team_elos[away] = new_away_elo
        
            games_played[home] += 1
            games_played[away] += 1
            
            # Progress logging
            if (i + 1) % 100 == 0:
                log.info(f"Processed {i + 1}/{len(games)} games...")
    
        log.info("=" * 60)
        log.info(f"Replay Complete: {len(predictions)} predictions generated")
        log.info("=" * 60)
        
        # Save predictions to database for Platt scaling
        log.info(f"Saving {len(predictions)} predictions to database...")
        saved_count = save_predictions(predictions, conn)
        log.info(f"[X] Saved {saved_count} predictions to live_predictions table")
        log.info("=" * 60)
    
        return predictions, team_elos


def save_elo_snapshot(
        game_id: int,
        game_date: date,
        team_elos: Dict[str, Decimal],
        games_played: Dict[str, int],
        season: str
):
    """
    Save ELO ratings for all teams as of a specific date.

    Args:
        game_date: The date these ELOs are valid for
        team_elos: Dict of team_code -> elo_rating
        games_played: Dict of team_code -> number of games played
        season: Season identifier (e.g., '2023-24')
    """
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            for team, elo in team_elos.items():
                cur.execute("""
                    INSERT INTO team_elo_history
                        (team_code, game_id, game_date, elo_rating, games_played, season)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (team_code, game_id)
                    DO UPDATE SET
                        elo_rating = EXCLUDED.elo_rating,
                        games_played = EXCLUDED.games_played
                """, (team, game_id, game_date, elo, games_played.get(team, 0), season))
                
            conn.commit()
    

def save_predictions(predictions: List[Dict], conn):
    """
    Save backtest predictions to live_predictions table.
    
    Args:
        predictions: List of prediction dicts from replay
        conn: Database connection (reuse from replay_elos)
    
    Returns:
        Number of predictions saved
    """
    if not predictions:
        return 0
    
    with conn.cursor() as cur:
        # Step 1: Get valid game_ids from game_features
        cur.execute("SELECT game_id FROM game_features")
        valid_game_ids = {row[0] for row in cur.fetchall()}
        
        # Step 2: Build rows list (only for games in game_features)
        rows = []
        skipped = 0
        for pred in predictions:
            # Skip predictions for games not in game_features
            if pred['game_id'] not in valid_game_ids:
                skipped += 1
                continue
                
            # Map prediction keys -> table columns
            rows.append((
                pred['game_id'],
                pred['game_date'],
                pred['home_elo_before'],
                pred['away_elo_before'],
                pred['predicted_home_win_prob'],
                pred['actual_home_won'],
                pred['prediction_correct'],
            ))
        
        if skipped > 0:
            log.info(f"  Skipped {skipped} predictions (games not in game_features)")
        
        # Step 2: Execute batch insert AFTER building rows
        for row in rows:
            cur.execute("""
                INSERT INTO live_predictions
                    (game_id, predicted_at, home_elo, away_elo,
                     predicted_home_win_prob, actual_home_won, prediction_correct)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (game_id) DO UPDATE SET
                    predicted_at = EXCLUDED.predicted_at,
                    home_elo = EXCLUDED.home_elo,
                    away_elo = EXCLUDED.away_elo,
                    predicted_home_win_prob = EXCLUDED.predicted_home_win_prob,
                    actual_home_won = EXCLUDED.actual_home_won,
                    prediction_correct = EXCLUDED.prediction_correct
            """, row)
            
        conn.commit()
        
    return len(predictions)
    
    

# ============================================================
# Main Entry Point
# ============================================================

def main():
    """
    Run ELO replay on 2023-24 season.

    You can customize the date range:
    - Full season: start_date='2023-10-10', end_date='2024-06-30'
    - One month test: start_date='2023-10-10', end_date='2023-11-10'
    """
    import sys
    
    # For initial testing, do just one month
    # Once verified, expand to full season
    test_mode = len(sys.argv) > 1 and sys.argv[1] == '--test'
    
    if test_mode:
        log.info("Running in TEST mode (1 month of games)")
        start = date(2024, 10, 10)
        end = date(2024, 11, 10)
    else:
        log.info("Running FULL season replay (2023-2026)")
        start = date(2023, 10, 1)  # Start of 2023-24 season
        end = date(2026, 6, 30)    # End of 2025-26 season
        
    # Run the replay
    predictions, final_elos = replay_elos(
        start_date=start,
        end_date=end,
        save_history=True
    )
    
    # Quick summary
    total_games = len(predictions)
    correct_predictions = sum(1 for p in predictions if p['prediction_correct'])
    accuracy = (correct_predictions / total_games * 100) if total_games > 0 else 0
    
    log.info("")
    log.info("Quick Summary:")
    log.info(f"  Total Games: {total_games}")
    log.info(f"  Correct Predictions: {correct_predictions}")
    log.info(f"  Simple Accuracy: {accuracy:.1f}%")
    log.info("")
    log.info("ELO history has been saved to team_elo_history table")
    log.info("Run model evaluation next to get detailed calibration analysis")

if __name__ == "__main__":
    main()