# pipelines/betting/show_today_predictions.py
"""
Display today's NHL game predictions with ELOs, probabilities, and edges.
Run this each morning to see what the model predicts for today's games.
"""
from __future__ import annotations
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import List, Dict
import psycopg

from pipelines.config import DATABASE_URL
from pipelines.common.logging_setup import setup as setup_logging

setup_logging("INFO")
log = logging.getLogger(__name__)

# ELO Configuration (matches your system)
HOME_ADV = Decimal("50")

def calculate_win_probability(home_elo: Decimal, away_elo: Decimal) -> Decimal:
    """
    Calculate home team win probability using ELO ratings.
    
    Formula: P(home wins) = 10^(diff/400) / (1 + 10^(diff/400))
    where diff = (home_elo + HOME_ADV) - away_elo
    """
    diff = (home_elo + HOME_ADV - away_elo) / Decimal("400")
    ten_pow = Decimal("10") ** diff
    prob = ten_pow / (Decimal("1") + ten_pow)
    return prob


def implied_prob_from_american(odds: int) -> Decimal:
    """
    Convert American odds to implied probability.
    
    Examples:
        -150 (favorite) -> 60% implied probability
        +125 (underdog) -> 44.4% implied probability
    """
    if odds < 0:
        return Decimal(str(abs(odds))) / (Decimal(str(abs(odds))) + Decimal("100"))
    else:
        return Decimal("100") / (Decimal(str(odds)) + Decimal("100"))


def get_upcoming_games() -> List[Dict]:
    """
    Get upcoming NHL games with ELOs, odds, and calculated edges.
 
    Returns list of game dicts with:
      - game_id, game_datetime
      - home_team, away_team
      - home_elo, away_elo
      - predicted_home_win_prob
      - best odds for each team
      - calculated edges
    """
    
    
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # Get upcoming games with ELOs and best odds
            cur.execute("""
                WITH latest_elos AS (
                    -- Get most recent ELO for each team
                    SELECT DISTINCT ON (team_code)
                        team_code,
                        elo_rating
                    FROM team_elo_history
                    ORDER BY team_code, game_date DESC, game_id DESC
                ),
                best_odds AS (
                    -- Get best available odds for each team (within 24 hours)
                    SELECT
                        game_id,
                        outcome,
                        MAX(american_odds) FILTER (WHERE american_odds > 0) as best_underdog_odds,
                        MAX(american_odds) FILTER (WHERE american_odds < 0) as best_favorite_odds
                    FROM odds_quotes
                    WHERE market = 'moneyline'
                      AND captured_at >= NOW() - INTERVAL '24 hours'
                    GROUP BY game_id, outcome
                )
                SELECT
                    gf.game_id,
                    gf.game_datetime_utc,
                    gf.home_team,
                    gf.away_team,
                    h_elo.elo_rating as home_elo,
                    a_elo.elo_rating as away_elo,
                    COALESCE(h_odds.best_favorite_odds, h_odds.best_underdog_odds) as home_odds,
                    COALESCE(a_odds.best_favorite_odds, a_odds.best_underdog_odds) as away_odds
                FROM game_features gf
                LEFT JOIN latest_elos h_elo ON h_elo.team_code = gf.home_team
                LEFT JOIN latest_elos a_elo ON a_elo.team_code = gf.away_team
                LEFT JOIN best_odds h_odds ON h_odds.game_id = gf.game_id AND h_odds.outcome = 'home'
                LEFT JOIN best_odds a_odds ON a_odds.game_id = gf.game_id AND a_odds.outcome = 'away'
                WHERE gf.game_datetime_utc > NOW()  -- Only upcoming games
                ORDER BY gf.game_datetime_utc
                LIMIT 20;  -- Show next 20 games
            """)
            
            rows = cur.fetchall()
            
    games = []
    for row in rows:
        game_id, game_dt, home, away, home_elo, away_elo, home_odds, away_odds = row
        
        if home_elo is None or away_elo is None:
            log.warning(f"Missing ELO for {home} vs {away}, skipping")
            continue
            
        # Convert to Decimal
        home_elo = Decimal(str(home_elo))
        away_elo = Decimal(str(away_elo))
        
        # Calculate predicted probability
        pred_home_win = calculate_win_probability(home_elo, away_elo)
        pred_away_win = Decimal("1") - pred_home_win
        
        # Calculate edges if odds available
        home_edge = None
        away_edge = None
        
        if home_odds:
            implied_home = implied_prob_from_american(home_odds)
            home_edge = pred_home_win - implied_home
            
        if away_odds:
            implied_away = implied_prob_from_american(away_odds)
            away_edge = pred_away_win - implied_away
            
        games.append({
            "game_id": game_id,
            "game_datetime": game_dt,
            "home_team": home,
            "away_team": away,
            "home_elo": home_elo,
            "away_elo": away_elo,
            "pred_home_win": pred_home_win,
            "pred_away_win": pred_away_win,
            "home_odds": home_odds,
            "away_odds": away_odds,
            "home_edge": home_edge,
            "away_edge": away_edge,
        })
        
    return games


def print_predictions(games: List[Dict]):
    """
    Print today's predictions in a readable format.
    """
    if not games:
        log.info("No games scheduled for today.")
        return
    
    print("=" * 100)
    print(f"UPCOMING NHL GAMES - PREDICTIONS & ODDS")
    print("=" * 100)
    print()
    
    for game in games:
        # Format game time - convert UTC to EST
        from datetime import timezone, timedelta
        est = timezone(timedelta(hours=-5))  # EST is UTC-5
        game_time_est = game["game_datetime"].astimezone(est)
        date_str = game_time_est.strftime("%b %d")
        time_str = game_time_est.strftime("%I:%M %p EST")
        
        # Team names and probabilities
        home = game["home_team"]
        away = game["away_team"]
        prob_home = float(game["pred_home_win"]) * 100
        prob_away = float(game["pred_away_win"]) * 100
        
        # ELOs
        elo_home = float(game["home_elo"])
        elo_away = float(game["away_elo"])
        
        # Odds
        odds_home = game["home_odds"] if game["home_odds"] else "N/A"
        odds_away = game["away_odds"] if game["away_odds"] else "N/A"
        
        # Format odds display
        if odds_home != "N/A":
            odds_home_str = f"{odds_home:+d}" if odds_home < 0 else f"{odds_home}"
        else:
            odds_home_str = "N/A"
            
        if odds_away != "N/A":
            odds_away_str = f"{odds_away:+d}" if odds_away < 0 else f"{odds_away}"
        else:
            odds_away_str = "N/A"
            
        # Edges
        edge_home = game["home_edge"]
        edge_away = game["away_edge"]
        
        # Determine betting recommendation
        bet_recommendation = ""
        if edge_home and edge_home > Decimal("0.05"):
            bet_recommendation = f" [BET {home}!]"
        elif edge_away and edge_away > Decimal("0.05"):
            bet_recommendation = f" [BET {away}!]"
            
        # Print game info
        print(f"{date_str} {time_str} | {away} @ {home}{bet_recommendation}")
        print(f"         Probabilities: {away} {prob_away:.1f}% | {home} {prob_home:.1f}%")
        print(f"         ELOs: {away} {elo_away:.0f} | {home} {elo_home:.0f}")
        print(f"         Best Odds: {away} {odds_away_str} | {home} {odds_home_str}")
        
        if edge_home is not None or edge_away is not None:
            edge_home_str = f"{float(edge_home)*100:+.1f}%" if edge_home else "N/A"
            edge_away_str = f"{float(edge_away)*100:+.1f}%" if edge_away else "N/A"
            print(f"         Edges: {away} {edge_away_str} | {home} {edge_home_str}")
        
        print()
    
    print("=" * 100)
    print(f"Total games today: {len(games)}")
    print("=" * 100)


def main():
    """Main entry point."""
    log.info("Fetching upcoming NHL games...")
    games = get_upcoming_games()
    print_predictions(games)


if __name__ == "__main__":
    main()
            