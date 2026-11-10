# pipelines/etl/backfill_goalie_data.py
import logging
import psycopg
from pipelines.config import DATABASE_URL
from pipelines.common.logging_setup import setup as setup_logging
from pipelines.etl.ingest_game_goalies import fetch_boxscore, extract_starting_goalies, upsert_game_goalies

setup_logging("INFO")
log = logging.getLogger(__name__)


def get_games_missing_goalies():
    """
    Find all games that don't have goalie assignments.
    
    Returns:
        List of game_ids that need backfilling
    """
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
            LEFT JOIN game_goalies gg ON gr.game_id = gg.game_id
            WHERE gg.game_id IS NULL
            ORDER BY gr.game_date ASC
        """)
        
        game_ids = [row[0] for row in cur.fetchall()]

    return game_ids


def main():
    """Backfill goalie data for all historical games."""
    log.info("=" * 80)
    log.info("GOALIE DATA BACKFILL")
    log.info("=" * 80)
    
    games_missing_goalies = get_games_missing_goalies()

    log.info(f"Found {len(games_missing_goalies)} games missing goalie data")
    log.info("")
    
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
        
        total = len(games_missing_goalies)
        for index, game_id in enumerate(games_missing_goalies, start=1):
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
                log.info(f"  PARTIAL: Missing goalie data")
                
            if index % 100 == 0:
                percent = (index / total) * 100
                log.info(f"Progress: {index}/{total} ({percent:.1f}%) - Last: {game_id}")

        conn.commit()

    log.info("")
    log.info("=" * 80)
    log.info(f"Processed {games_processed} games")
    log.info(f"Found complete goalie data for {goalies_found} games")
    log.info("=" * 80)


if __name__ == "__main__":
    main()
