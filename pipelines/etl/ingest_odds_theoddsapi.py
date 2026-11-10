from __future__ import annotations

import os, logging, requests
import datetime as dtm
from decimal import Decimal
from requests.exceptions import RequestException
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from pipelines.config import DATABASE_URL
from pipelines.common.db import connect, execute_many
from pipelines.common.logging_setup import setup as setup_logging
from typing import Optional

# ---------- Logging ----------
setup_logging("INFO")
log = logging.getLogger(__name__)


# ---------- Config ----------
THEODDS_API_KEY = os.getenv("THEODDS_API_KEY")
THEODDS_REGION  = os.getenv("THEODDS_REGION", "us")
BOOKS_ALLOW  = [s.strip() for s in os.getenv("BOOKS", "").split(",") if s.strip()]
POINT_SCALE = int(os.getenv("POINT_SCALE", "100"))  # -1.5 -> -150, 6.0 -> 600

if not THEODDS_API_KEY:
    raise RuntimeError("Set ODDS_API_KEY in pipelines/.env")

# Map The Odds API market keys to our DB values
MARKET_MAP = {
    "h2h": "moneyline",         # moneyline
    "spreads": "spread",        # spread
    "totals": "total",          # over/under
    }

# NHL team full name -> abbreviation (matches game_features.home_team / away_team)
TEAM_TO_ABBR = {
    "Anaheim Ducks": "ANA",
    "Arizona Coyotes": "ARI",
    "Boston Bruins": "BOS",
    "Buffalo Sabres": "BUF",
    "Calgary Flames": "CGY",
    "Carolina Hurricanes": "CAR",
    "Chicago Blackhawks": "CHI",
    "Colorado Avalanche": "COL",
    "Columbus Blue Jackets": "CBJ",
    "Dallas Stars": "DAL",
    "Detroit Red Wings": "DET",
    "Edmonton Oilers": "EDM",
    "Florida Panthers": "FLA",
    "Los Angeles Kings": "LAK",
    "Minnesota Wild": "MIN",
    "Montreal Canadiens": "MTL",
    "Nashville Predators": "NSH",
    "New Jersey Devils": "NJD",
    "New York Islanders": "NYI",
    "New York Rangers": "NYR",
    "Ottawa Senators": "OTT",
    "Philadelphia Flyers": "PHI",
    "Pittsburgh Penguins": "PIT",
    "San Jose Sharks": "SJS",
    "Seattle Kraken": "SEA",
    "St. Louis Blues": "STL",
    "Tampa Bay Lightning": "TBL",
    "Toronto Maple Leafs": "TOR",
    "Utah Mammoth": "UTA",
    "Vancouver Canucks": "VAN",
    "Vegas Golden Knights": "VGK",
    "Washington Capitals": "WSH",
    "Winnipeg Jets": "WPG",
    }

# ---------- HTTP fetch with retries ----------
@retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError)),
)
def fetch_odds() -> list[dict]:
    url = "https://api.the-odds-api.com/v4/sports/icehockey_nhl/odds"
    params = {
        "apiKey": THEODDS_API_KEY,
        "regions": THEODDS_REGION,
        "markets": "h2h,spreads,totals",    # moneyline, spread, total
        "oddsFormat": "american",
        "dateFormat": "iso",
    }
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    
    # Log API usage from response headers
    requests_used = r.headers.get('x-requests-used', 'unknown')
    requests_remaining = r.headers.get('x-requests-remaining', 'unknown')
    log.info(f"TheOddsAPI Usage: {requests_used} used, {requests_remaining} remaining")

    return r.json()

# ---------- Helpers ----------
def _scaled_point(val) -> int | None:
    if val is None:
        return None
    return int(Decimal(str(val)) * POINT_SCALE)

def _normalize_outcome(market_key: str, outcome_name: str, game: dict) -> Optional[str]:
    """
    h2h/spreads: outcome is team name -> 'home' or 'away'
    totals: outcome is 'Over'/'Under' -> 'over'/'under'
    """
    if market_key in ("h2h", "spreads"):
        if outcome_name == game.get("home_team"):
            return "home"
        if outcome_name == game.get("away_team"):
            return "away"
        return None
    if market_key == "totals":
        n = (outcome_name or "").lower()
        if "over" in n:
            return "over"
        if "under" in n:
            return "under"
        return None
    return None

def _iso_to_date_utc(iso_str: str) -> dtm.date:
    # The Odds API uses ISO8601 with 'Z'
    try:
        dt_obj = dtm.datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except ValueError:
        from email.utils import parsedate_to_datetime
        dt_obj = parsedate_to_datetime(iso_str)
    return dt_obj.astimezone(dtm.timezone.utc).date()

def to_abbr(name: str | None) -> str | None:
    return TEAM_TO_ABBR.get(name or "")

def resolve_game_id(game: dict, cur) -> Optional[int]:
    """
    Resolve our numeric game_id by matching (date ±1, home abbr, away abbr)
    against game_features. Returns None if not found.
    """
    home_abbr = to_abbr(game.get("home_team"))
    away_abbr = to_abbr(game.get("away_team"))
    if not home_abbr or not away_abbr:
        log.debug("Unknown team names: %s vs %s", home_abbr, away_abbr)
        return None
    
      
    commence = game.get("commence_time")  # ISO
    if not commence:
        return None
    
    d = _iso_to_date_utc(commence)
    d0 = d - dtm.timedelta(days=1)
    d1 = d + dtm .timedelta(days=1)
    
    cur.execute(
        """
        SELECT game_id
          FROM game_features
         WHERE game_datetime_utc::date BETWEEN %s AND %s
           AND home_team = %s
           AND away_team = %s
         ORDER BY game_datetime_utc
         LIMIT 1;
        """,
        (d - dtm.timedelta(days=1), d + dtm.timedelta(days=1), home_abbr, away_abbr),
    )
    row = cur.fetchone()
    return row[0] if row else None

# ---------- SQL ----------
UPSERT_SQL = """
INSERT INTO odds_quotes (game_id, book, market, outcome, american_odds, line_number, captured_at)
VALUES (%s, %s, %s, %s, %s, %s, now())
ON CONFLICT (game_id, book, market, outcome, captured_minute_utc, line_key)
DO NOTHING;
"""

# ---------- Parse payload -> rows ----------
def parse_rows(payload: list[dict],cur) -> list[tuple]:
    """
    rows: (game_id, book, market, outcome, american_odds, line_number)
    """
    out_rows: list[tuple] = []
    
    for game in payload:
        gid = resolve_game_id(game, cur)
        if gid is None:
            # Not found yet in game_features; schedule ingest may need to run first
            log.debug("Skip event (unresolved game_id): %s vs %s at %s",
                      game.get("home_team"), game.get("away_team"), game.get("commence_time"))
            continue
            
        for b in game.get("bookmakers", []):
            book = b.get("title") or b.get("key") or "Unknown"
            if BOOKS_ALLOW and book not in BOOKS_ALLOW:
                continue
                
            for m in b.get("markets", []):
                mk_raw = m.get("key")
                if mk_raw not in MARKET_MAP:
                    continue
                market = MARKET_MAP[mk_raw]
                
                for out in m.get("outcomes", []):
                    outcome_name = out.get("name") or out.get("description") or ""
                    outcome = _normalize_outcome(mk_raw, outcome_name, game)
                    if outcome is None:
                        continue
                        
                    price = out.get("price")
                    if price is None:
                        continue
                    try:
                        american_odds = int(price)
                    except Exception:
                        continue
                        
                    line_number = None
                    if mk_raw in ("spreads", "totals"):
                        line_number = _scaled_point(out.get("point"))
                        
                    out_rows.append((gid, book, market, outcome, american_odds, line_number))
                    
    return out_rows

# ---------- Main ----------
def main():
    payload = fetch_odds()
    if not isinstance(payload, list):
        log.error("Unexpected payload type: %s", type(payload))
        return
    
    total = 0
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            rows = parse_rows(payload, cur)
            if not rows:
                log.warning("No rows parsed; run schedule ingest first or widen date window.")
                return
            total = execute_many(cur, UPSERT_SQL, rows)
        conn.commit()
        
    log.info("Upserted %s odds_quotes rows", total)
    
if __name__ == "__main__":
    main()