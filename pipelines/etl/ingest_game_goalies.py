# pipelines/etl/ingest_game_goalies.py
from __future__ import annotations
import logging, requests
from datetime import date, timedelta
import psycopg
from pipelines.config import DATABASE_URL
from pipelines.common.db import execute_many
from pipelines.common.logging_setup import setup as setup_logging

from pipelines.common.db import connect

setup_logging("INFO")
log = logging.getLogger(__name__)

BASE = "https://api-web.nhle.com/v1"


def fetch_boxscore(game_id: int):
    """
    Fetch boxscore data from NHL API.
    
    Args:
        game_id: NHL game ID (e.g., 2025020903)
      
    Returns:
        Boxscore JSON dict, or None if game not found/not finished
    """
    try:
        r = requests.get(f"{BASE}/gamecenter/{game_id}/boxscore", timeout=20)
        r.raise_for_status()
        data = r.json()
        return data
    
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            log.debug(f"No game found for {game_id}")
            return None
        else:
            log.error(f"Error fetching boxscore for {game_id}: {e}")
            return None
        
    except Exception as e:
        log.error(f"Failed to boxscore stats for game {game_id}: {e}")
        return None


def extract_starting_goalies(boxscore: dict):
    """
    Extract starting goalie info from boxscore JSON.
    
    Args:
        boxscore: Boxscore JSON from NHL API
    
    Returns:
        Tuple of (home_goalie_info, away_goalie_info)
        Each is a dict with keys: player_id, name
        Returns (None, None) if data not available
    """
    try:
        home_goalie_info = {}
        away_goalie_info = {}
        
        # First, navigate to playerByGameStats
        player_stats = boxscore.get("playerByGameStats", {})
        
        # Get the home team's goalie list
        home_goalies = player_stats.get("homeTeam", {}).get('goalies', [])
        
        # Get the away team's goalie list
        away_goalies = player_stats.get("awayTeam", {}).get('goalies', [])
        
        # Find home starting goalie
        for goalie in home_goalies:
            if goalie.get("starter") == True:
                home_goalie_info = {
                    "player_id": goalie.get("playerId"),
                    "name": goalie.get("name", {}).get("default", "Unknown")
                }
                break
                
        for goalie in away_goalies:
            if goalie.get("starter") == True:
                away_goalie_info = {
                    "player_id": goalie.get("playerId"),
                    "name": goalie.get("name", {}).get("default", "Unknown")
                }
                break
                
        if not home_goalie_info:
            home_goalie_info = None
        if not away_goalie_info:
            away_goalie_info = None
        
        return (home_goalie_info, away_goalie_info)
    
    except Exception as e:
        log.error(f"Error extracting goalie info: {e}")
        return (None, None)


def upsert_game_goalies(conn, game_id: int, home_goalie: dict, away_goalie: dict):
    """
    Insert or update game_goalies table with starting goalie assignments.
    
    Args:
        conn: Database connection
        game_id: NHL game ID
        home_goalie: Dict with player_id and name (or None)
        away_goalie: Dict with player_id and name (or None)
    """
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO game_goalies (
                game_id,
                home_goalie_id,
                home_goalie_name,
                away_goalie_id,
                away_goalie_name,
                home_goalie_confirmed,
                away_goalie_confirmed,
                confirmed_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, NOW()
            )
            ON CONFLICT (game_id) DO UPDATE SET
                home_goalie_id = EXCLUDED.home_goalie_id,
                home_goalie_name = EXCLUDED.home_goalie_name,
                away_goalie_id = EXCLUDED.away_goalie_id,
                away_goalie_name = EXCLUDED.away_goalie_name,
                home_goalie_confirmed = EXCLUDED.home_goalie_confirmed,
                away_goalie_confirmed = EXCLUDED.away_goalie_confirmed,
                confirmed_at = NOW()
        """, (
             game_id,
             home_goalie['player_id'] if home_goalie else None,
             home_goalie['name'] if home_goalie else None,
             away_goalie['player_id'] if away_goalie else None,
             away_goalie['name'] if away_goalie else None,
             home_goalie is not None,  # Boolean: True if we have data
             away_goalie is not None,  # Boolean: True if we have data
        ))


def main():
    """Fetch and store starting goalie data for recent games."""
    log.info("=" * 80)
    log.info("GAME GOALIES INGESTION")
    log.info("=" * 80)
    
    # start = date.today() - timedelta(days=3)  # default is 3
    start = date(2023, 10, 1)
    
    games_processed = 0
    goalies_found = 0
    
    # Use psycopg.connect() with DATABASE_URL
    with psycopg.connect(
        DATABASE_URL,
        sslmode="require",
        prefer_query_mode=None,
        prepare_threshold=None,
        prepared_statement_cache_queries=None,
    ) as conn, conn.cursor() as cur:
            
        cur.execute("""
            SELECT gr.game_id
            FROM game_results gr
            INNER JOIN game_features gf ON gf.game_id = gr.game_id
            WHERE gr.game_date >= %s
            ORDER BY gr.game_date DESC
        """, (start,))

        game_ids = [row[0] for row in cur.fetchall()]
            
        log.info(f"Found {len(game_ids)} games to process")
        log.info("")
            
        for game_id in game_ids:
            log.info(f"Processing {game_id}...")
                
            # Step 1: Fetch boxscore
            boxscore = fetch_boxscore(game_id)
                
            # Step 2: Check if we have data
            if not boxscore:
                log.info(f"  SKIP: No boxscore found")
                continue
                    
            # Step 3: Extract starting goalies
            home_goalie, away_goalie = extract_starting_goalies(boxscore)
                
            # Step 4: Save to database
            upsert_game_goalies(conn, game_id, home_goalie, away_goalie)
            games_processed += 1
                
            # Step 5: Log what we found
            if home_goalie and away_goalie:
                log.info(f"  OK: {home_goalie['name']} vs {away_goalie['name']}")
                goalies_found += 1
            else:
                log.info(f"  PARTIAL:Missing goalie data")
                    
                    
        conn.commit()
            
            
    log.info("")
    log.info("=" * 80)
    log.info(f"Processed {games_processed} games")
    log.info(f"Found complete goalie data for {goalies_found} games")
    log.info("=" * 80)
    
    
if __name__ == "__main__":
    main()

# if __name__ == "__main__":
#     main()
#     # Test both functions together
#     print("Testing fetch_boxscore...")
#     box = fetch_boxscore(2025020903)
#
#     if box:
#         print("[x] Boxscore fetched successfully")
#         print()
#
#         print("Testing extract_starting_goalies...")
#         home, away = extract_starting_goalies(box)
#
#         if home and away:
#             print(f"[x] Home starter: {home['name']} (ID: {home['player_id']})")
#             print(f"[x] Away starter: {away['name']} (ID: {away['player_id']})")
#         else:
#             print("[-] Could not extract goalies")
#     else:
#         print("[-] Failed to fetch boxscore")
