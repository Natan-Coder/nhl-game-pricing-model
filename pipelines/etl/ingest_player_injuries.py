# pipelines/etl/ingest_player_injuries.py
"""
Ingest player injuries from NHL injury web scrape.
Fetches active injuries in the NHL and updates player injury table,
    if player is not on the list they are uninjured
Run daily to keep stats current.
"""
import os, logging, requests
from pipelines.config import DATABASE_URL
from pipelines.common.logging_setup import setup as setup_logging
from bs4 import BeautifulSoup
import psycopg
from pipelines.common.team_mappings import HOCKEY_REFERENCE_TO_ABBR as TEAM_TO_ABBR


setup_logging("INFO")
log = logging.getLogger(__name__)


def fetch_current_injuries() -> list[dict]:
    """
    Fetches Hockey-Reference injury table
    
    Returns list of current injuries
    
    """
    # Fetch the HTML page
    url = "https://www.hockey-reference.com/friv/injuries.cgi"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    
    # Parse the injuries
    injuries = parse_injuries_table(r.text)
    
    # Display results
    log.info(f"Found {len(injuries)} injured players")
    
    return injuries



def parse_injuries_table(html_content: str) -> list[dict]:
    """
    Parse Hockey-Reference injury table HTML
    
    Returns list of dicts with keys:
    - player_name
    - team
    - date_injured
    - injury_type
    - injury_note
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    table = soup.find('table', id='injuries')
    tbody = table.find('tbody')
    rows = tbody.find_all('tr')
    
    injuries = []
    
    for row in rows:
        if 'thead' in row.get('class', []):
            continue
        
        # Find cells by data-stat attribute
        player_cell = row.find(attrs={'data-stat': 'player'})
        player_name = player_cell.find('a').text if player_cell else None
        team_cell = row.find(attrs={'data-stat': 'team_name'})
        team_full_name = team_cell.find('a').text if team_cell else None
        team_abbr = TEAM_TO_ABBR.get(team_full_name, "UNK")  # Map to abbreviation!
        #team = team_cell.find('a').text if team_cell else None
        date_cell = row.find(attrs={'data-stat': 'date_injury'})
        date_injured = date_cell.get('csk') if date_cell else None
        injury_cell = row.find(attrs={'data-stat': 'injury_type'})
        injury_type = injury_cell.text.strip() if injury_cell else None
        note_cell = row.find(attrs={'data-stat': 'injury_note'})
        injury_note = note_cell.text.strip() if note_cell else None
        
        injury = {
            'player_name': player_name,
            'team': team_abbr,
            'date_injured': date_injured,
            'injury_type': injury_type,
            'injury_note': injury_note
            }
        injuries.append(injury)
    
    return injuries


def insert_new_injury(conn, injury):
    """
    Insert a new injury record for a player.
    Sets is_current=TRUE, first_seen_at and last_seen_at to NOW().
    """
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO player_injuries (
                player_name,
                team_abbr,
                date_injured,
                injury_type,
                injury_note,
                is_current,
                first_seen_at,
                last_seen_at
            ) VALUES (
                %s, %s, %s, %s, %s, TRUE, NOW(), NOW()
            )
            
        """, (
            injury['player_name'],
            injury['team'],
            injury['date_injured'],
            injury['injury_type'],
            injury['injury_note']
        ))
        
        
def update_still_injured(conn, player_name: str):
    """
    Update still injured players table
    """
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE player_injuries
            SET last_seen_at = NOW()
            WHERE player_name = %s AND is_current = TRUE
        """, (player_name,))
    

def mark_returned(conn, player_name: str):
    """
    Update injured players table as player returned
    """
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE player_injuries
            SET is_current = FALSE, returned_at = NOW()
            WHERE player_name = %s AND is_current = TRUE
        """, (player_name,))
        
        
def get_db_current_injuries(conn):
    """
    Query database for current injuries table
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT player_name, team_abbr, date_injured, injury_type, injury_note
            FROM player_injuries
            WHERE is_current = TRUE
        """)
        rows = cur.fetchall()
        
        injuries = {}
        for row in rows:
            player_name = row[0]  # First column from SELECT
            injuries[player_name] = {
                'team_abbr': row[1],
                'date_injured': row[2],
                'injury_type': row[3],
                'injury_note': row[4]
                }
    return injuries


def main():
    """Fetch and store current injuries in the league"""
    log.info("=" * 80)
    log.info("NHL CURRENT INJURIES INGESTION")
    log.info("=" * 80)
    
    
    injuries = fetch_current_injuries()
    
    scraped_players = {inj['player_name'] for inj in injuries}
    log.info(f"Scraped {len(injuries)} current injuries")
    
    with psycopg.connect(
            DATABASE_URL,
            sslmode="require",
            prefer_query_mode=None,
            prepare_threshold=None,
            prepared_statement_cache_queries=None,
    ) as conn:
        
        # Get current injuries from database
        db_current = get_db_current_injuries(conn)
        db_players = set(db_current.keys())
        log.info(f"Found {len(db_players)} current injuries in database")
        
        # Detect changes by comparing sets
        new_players = scraped_players - db_players
        still_injured = scraped_players & db_players
        returned_players = db_players - scraped_players
        
        log.info(f"Detected {len(new_players)} new injuries")
        log.info(f"Detected {len(still_injured)} players still injured")
        log.info(f"Detected {len(returned_players)} players returned to play")
        
        # Apply updates - handle new injuries
        for injury in injuries:
            if injury['player_name'] in new_players:
                log.info(f"  NEW: {injury['player_name']} ({injury['team']}) - {injury['injury_type']}")
                insert_new_injury(conn, injury)
                
        # Update players still injured
        for player_name in still_injured:
            log.info(f"  STILL INJURED: {player_name}")
            update_still_injured(conn, player_name)
            
        # Mark players as returned
        for player_name in returned_players:
            log.info(f"  RETURNED: {player_name}")
            mark_returned(conn, player_name)
            
        # Commit all changes
        conn.commit()
        
    log.info("")
    log.info("=" * 80)
    log.info(f"SUMMARY: {len(new_players)} new, {len(still_injured)} ongoing, {len(returned_players)} returned")
    log.info("=" * 80)
    
    
if __name__ == "__main__":
    main()