# pipelines/etl/ingest_goalie_stats.py
"""
Ingest goalie statistics from NHL API.
Fetches season stats for all goalies and updates goalie_stats table.
Run daily to keep stats current.
"""
from __future__ import annotations
import logging
import requests
import time
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
import psycopg
import argparse

from pipelines.config import DATABASE_URL
from pipelines.common.db import connect
from pipelines.common.logging_setup import setup as setup_logging
from pipelines.common.team_mappings import HOCKEY_REFERENCE_TO_ABBR as TEAM_TO_ABBR

setup_logging("INFO")
log = logging.getLogger(__name__)

# NHL team abbreviations (31 teams - ARI relocated to UTA in 2024-25)
# NHL_TEAMS = [
    "ANA", "BOS", "BUF", "CAR", "CBJ", "CGY", "CHI", "COL", "DAL", "DET",
    "EDM", "FLA", "LAK", "MIN", "MTL", "NJD", "NSH", "NYI", "NYR", "OTT",
    "PHI", "PIT", "SEA", "SJS", "STL", "TBL", "TOR", "VAN", "VGK", "WPG",
    "WSH"
]

# Current season (format: 20252026 for 2025-26 season)
#  CURRENT_SEASON = 20252026

def get_team_roster(team_abbr: str) -> Dict:
    """Fetch current roster for a team from NHL API."""
    url = f"https://api-web.nhle.com/v1/roster/{team_abbr}/current"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        log.error(f"Failed to fetch roster for {team_abbr}: {e}")
        return {}
    
    
def get_goalie_stats(player_id: int) -> Optional[Dict]:
    """Fetch detailed stats for a goalie from NHL API."""
    url = f"https://api-web.nhle.com/v1/player/{player_id}/landing"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Extract current season stats
        if 'featuredStats' in data and 'regularSeason' in data['featuredStats']:
            stats = data['featuredStats']['regularSeason']['subSeason']
            return {
                'player_id': player_id,
                'name': f"{data.get('firstName', {}).get('default', '')} {data.get('lastName', {}).get('default', '')}",
                'team': data.get('currentTeamAbbrev', ''),
                'games_played': stats.get('gamesPlayed', 0),
                'games_started': stats.get('gamesStarted', 0),
                'saves': stats.get('saves', 0),
                'shots_against': stats.get('shotsAgainst', 0),
                'goals_against': stats.get('goalsAgainst', 0),
                'save_pct': stats.get('savePctg', 0.0),
                'gaa': stats.get('goalsAgainstAvg', 0.0),
                'wins': stats.get('wins', 0),
                'losses': stats.get('losses', 0),
                'ot_losses': stats.get('otLosses', 0),
                'shutouts': stats.get('shutouts', 0),
                'toi_seconds': stats.get('timeOnIce', 0)
            }
    except Exception as e:
        log.error(f"Failed to fetch stats for player {player_id}: {e}")
    return None

def upsert_goalie_stats(conn, goalie_stats: Dict, season: int):
    """Insert or update goalie stats in database."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO goalie_stats (
                goalie_id, goalie_name, team_abbr, season,
                games_played, games_started, saves, shots_against,
                goals_against, save_pct, gaa, wins, losses,
                ot_losses, shutouts, time_on_ice_seconds, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
            )
            ON CONFLICT (goalie_id, season) DO UPDATE SET
                goalie_name = EXCLUDED.goalie_name,
                team_abbr = EXCLUDED.team_abbr,
                games_played = EXCLUDED.games_played,
                games_started = EXCLUDED.games_started,
                saves = EXCLUDED.saves,
                shots_against = EXCLUDED.shots_against,
                goals_against = EXCLUDED.goals_against,
                save_pct = EXCLUDED.save_pct,
                gaa = EXCLUDED.gaa,
                wins = EXCLUDED.wins,
                losses = EXCLUDED.losses,
                ot_losses = EXCLUDED.ot_losses,
                shutouts = EXCLUDED.shutouts,
                time_on_ice_seconds = EXCLUDED.time_on_ice_seconds,
                updated_at = NOW()
        """, (
            goalie_stats['player_id'],
            goalie_stats['name'],
            goalie_stats['team'],
            season,
            goalie_stats['games_played'],
            goalie_stats['games_started'],
            goalie_stats['saves'],
            goalie_stats['shots_against'],
            goalie_stats['goals_against'],
            goalie_stats['save_pct'],
            goalie_stats['gaa'],
            goalie_stats['wins'],
            goalie_stats['losses'],
            goalie_stats['ot_losses'],
            goalie_stats['shutouts'],
            goalie_stats['toi_seconds']
        ))
        
        
def main():
    """Main ingestion process."""
    parser = argparse.ArgumentParser(description='Ingest goalie stats')
    parser.add_argument('--season', type=int, default=20252026,
                        help='Season in formatt YYYYYYYY (e.g., 20230224)')
    args = parser.parse_args()
    
    season = args.season
    
    log.info("=" * 80)
    log.info("GOALIE STATS INGESTION")
    log.info("=" * 80)
    log.info(f"Season: {season}")
    log.info("")
    
    goalies_processed = 0
    goalies_updated = 0
    
    with connect(DATABASE_URL) as conn:
        for team_abbr in TEAM_TO_ABBR:
            log.info(f"Fetching roster for {team_abbr}...")
            roster = get_team_roster(team_abbr)
            
            if not roster or 'goalies' not in roster:
                log.warning(f"  No goalie data found for {team_abbr}")
                continue
            
            goalies = roster['goalies']
            log.info(f"  Found {len(goalies)} goalies")
            
            for goalie in goalies:
                player_id = goalie.get('id')
                if not player_id:
                    continue
                
                goalie_name = f"{goalie.get('firstName', {}).get('default', '')} {goalie.get('lastName', {}).get('default', '')}"
                log.info(f"    Fetching stats for {goalie_name} ({player_id})...")
                
                time.sleep(0.5)  # 500ms delay between goalie requests
                
                stats = get_goalie_stats(player_id)
                if stats and stats['games_played'] > 0:
                    upsert_goalie_stats(conn, stats, season)
                    goalies_updated += 1
                    log.info(f"      OK: {stats['games_played']}GP, {stats['save_pct']:.3f} SV%")
                else:
                    log.info(f"      SKIP: No games played yet")
                
                goalies_processed += 1
                
        time.sleep(1.0)  # 1s delay between teams
                
        conn.commit()
    
    log.info("")
    log.info("=" * 80)
    log.info(f"Processed {goalies_processed} goalies")
    log.info(f"Updated {goalies_updated} goalies with stats")
    log.info("=" * 80)
    log.info("")

if __name__ == "__main__":
    main()
