# pipelines/etl/ingest_schedule.py
from __future__ import annotations

import sys
import logging
from datetime import date, timedelta, datetime
import requests
import pytz


from pipelines.common.logging_setup import setup as setup_logging
from pipelines.common.db import connect, execute_one, execute_many
from pipelines.config import DATABASE_URL  # make sure this is set to your PG conn string

setup_logging("INFO")
log = logging.getLogger(__name__)

BASE = "https://api-web.nhle.com/v1"

# By default keep only regular season games (2). Change to {1,2,3} if you want all.
ALLOWED_GAME_TYPES = {2,3}

# ---------- UPSERT INTO DB ----------
SQL_UPSERT = """
INSERT INTO public.game_features
  (game_id, game_date, game_datetime_utc, home_team, away_team, venue, game_type)
VALUES
  (%s, %s::date, %s::timestamptz, %s, %s, %s, %s)
ON CONFLICT (game_id) DO UPDATE SET
  game_date         = EXCLUDED.game_date,
  game_datetime_utc = EXCLUDED.game_datetime_utc,
  home_team         = EXCLUDED.home_team,
  away_team         = EXCLUDED.away_team,
  venue             = EXCLUDED.venue,
  game_type         = EXCLUDED.game_type;
"""

def fetch_schedule_day(d: date) -> list[dict]:
    """Return list of game dicts for a single calendar date."""
    url = f"{BASE}/schedule/{d.isoformat()}"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    data = r.json()
    
    games: list[dict] = []
    # Common shape: {"gameWeek":[{"date":"YYYY-MM-DD","games":[...]} , ... ]}
    if isinstance(data, dict) and "gameWeek" in data:
        for day_block in data.get("gameWeek", []):
            games.extend(day_block.get("games", []))
    # Sometimes the site returns just {"games":[...]}
    elif isinstance(data, dict) and isinstance(data.get("games"), list):
        games = data["games"]
    return games

def extract_game_row(g: dict) -> dict:
    """Normalize fields you’ll insert/upsert into your DB."""
    gid = g.get("id") or g.get("gameId")  # 10-digit season-style id (e.g., 2025020001)
    if gid is None:
        return None
    try:
        gid = int(gid)
    except Exception:
        return None
    
    ts = g.get("startTimeUTC")     # e.g., "2025-10-14T23:00:00Z"
    if not ts:
        return None
    
    home = (g.get("homeTeam") or {}).get("abbrev")
    away = (g.get("awayTeam") or {}).get("abbrev")
    if not home or not away:
        return None
    
    venue = (g.get("venue") or {}).get("default") or None
    # gameType: 1=preseason, 2=regular, 3=playoffs (consistent with NHL)
    game_type = g.get("gameType")
    if ALLOWED_GAME_TYPES and game_type not in ALLOWED_GAME_TYPES:
        return None
    
    game_date = None
    if ts:
        # Parse UTC timestamp
        dt_utc = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        # Convert to Eastern Time
        eastern = pytz.timezone('America/New_York')
        dt_local = dt_utc.astimezone(eastern)
        # Extract local date
        game_date = dt_local.strftime("%Y-%m-%d")
    
    # IMPORTANT: use keys that match the SQL placeholders above
    return {
        "game_id": gid,
        "game_datetime_utc": ts,    # parsed in SQL as timestamptz
        "game_date": game_date,     # "YYYY-MM-DD"
        "home_team": home,
        "away_team": away,
        "venue": venue,
        "game_type": game_type,
    }

def fetch_range(start: date, end: date) -> list[dict]:
    all_games: list[dict] = []
    d = start
    while d <= end:
        day_games = fetch_schedule_day(d)
        if day_games:
            log.info("Found %d games on %s", len(day_games), d)
            all_games.extend(day_games)
        else:
            log.info("No games on %s", d)
        d += timedelta(days=1)
        
    rows: list[dict] = []
    skipped = 0
    for g in all_games:
        row = extract_game_row(g)
        if row:
            rows.append(row)
        else:
            skipped += 1
            
    log.info("Prepared %d rows (skipped %d due to filters/missing fields)", len(rows), skipped)
    if rows:
        sample = {k: rows[0][k] for k in rows[0]}
        log.debug("Sample prepared row: %s", sample)
    return rows

def ensure_unique_constraint():
    """Make sure a unique constraint on (game_id) exists for the upsert."""
    ddl = """
    CREATE UNIQUE INDEX IF NOT EXISTS ux_game_features_game_id
      ON public.game_features (game_id);
    """
    # open connection that already has prepare_threshold=0
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            execute_one(cur, ddl)
        conn.commit()

def upsert_games(rows: list[dict]) -> int:
    params = [
        (
            r["game_id"],
            r["game_date"],
            r["game_datetime_utc"],
            r["home_team"],
            r["away_team"],
            r["venue"],
            r["game_type"],
        )
        for r in rows
        if r.get("game_id") and r.get("game_date") and r.get("game_datetime_utc")
           and r.get("home_team") and r.get("away_team")
    ]
    if not params:
        return 0
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            total = execute_many(cur, SQL_UPSERT, params)
        conn.commit()
    return total or 0

def main():
    # window is up to you; this is a reasonable default
    start = date.today() - timedelta(days=1)
    end = date.today() + timedelta(days=4)
    
    log.info("Fetching schedule for %s to %s", start, end)
    rows = fetch_range(start, end)
    if not rows:
        log.info("No games found in window.")
        sys.exit(0)
    
    ensure_unique_constraint()
    written = upsert_games(rows)
    log.info("Upserted %d games into game_features.", written)
    
if __name__ == "__main__":
    main()