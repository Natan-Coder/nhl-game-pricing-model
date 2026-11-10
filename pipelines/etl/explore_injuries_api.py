# pipelines/etl/explore_injuries_api.py
"""
Exploration script to understand BALLDONTLIE injury API structure.
This helps us design the database schema.
"""

import os, logging, requests
import json
from requests.exceptions import RequestException
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from pipelines.config import DATABASE_URL
from pipelines.common.db import connect, execute_many
from pipelines.common.logging_setup import setup as setup_logging
from typing import Optional
from bs4 import BeautifulSoup
from pipelines.common.team_mappings import HOCKEY_REFERENCE_TO_ABBR as TEAM_TO_ABBR

setup_logging("INFO")
log = logging.getLogger(__name__)

# ---------- Config ----------
BALLDONTLIE_API_KEY = os.getenv("BALLDONTLIE_API_KEY")
# ...
if not BALLDONTLIE_API_KEY:
    raise RuntimeError("Set BALLDONTLIE_API_KEY in pipelines/.env")



# ---------- HTTP fetch with retries ----------
@retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError)),
)


def fetch_injuries() -> list[dict]:
    url = "https://api.balldontlie.io/nhl/v1/player_injuries"
    headers = {"Authorization": BALLDONTLIE_API_KEY}
    r = requests.get(url, headers=headers, timeout=15)
    
    # Debug: Log what we got back
    if r.status_code != 200:
        log.error(f"API returned status {r.status_code}")
        log.error(f"Response body: {r.text}")
        log.error(f"Response headers: {dict(r.headers)}")

    r.raise_for_status()


    # Log API usage from response headers
    requests_used = r.headers.get('x-requests-used', 'unknown')
    requests_remaining = r.headers.get('x-requests-remaining', 'unknown')
    log.info(f"BALLDONTLIE API Usage: {requests_used} used, {requests_remaining} remaining")
    
    return r.json()


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

# ---------- Main ----------
def main():
    log.info("Fetching injuries from Hockey-Reference...")
    
    # Debug: Check if API key is loaded
    # log.info(f"API Key loaded: {BALLDONTLIE_API_KEY[:10]}..." if BALLDONTLIE_API_KEY else "API Key: NOT FOUND")
    # injuries = fetch_injuries()
    #
    # print(json.dumps(injuries, indent=2))
    
    # Fetch the HTML page
    url = "https://www.hockey-reference.com/friv/injuries.cgi"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    
    # Parse the injuries
    injuries = parse_injuries_table(r.text)
    
    
    # Display results
    log.info(f"Found {len(injuries)} injured players")
    
    # Show first 3 as examples
    for injury in injuries[:3]:
        print(json.dumps(injury, indent=2))

if __name__ == "__main__":
    main()
    






