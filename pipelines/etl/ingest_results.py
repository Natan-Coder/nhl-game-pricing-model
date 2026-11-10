# pipelines/etl/ingest_results.py
from __future__ import annotations
import logging, requests
from datetime import date, timedelta
import psycopg
from pipelines.config import DATABASE_URL
from pipelines.common.db import execute_many
from pipelines.common.logging_setup import setup as setup_logging

setup_logging("INFO")
log = logging.getLogger(__name__)

BASE = "https://api-web.nhle.com/v1"

SQL_UPSERT = """
INSERT INTO game_results (game_id, game_date, home_team, away_team, home_goals, away_goals, decided_in_ot_so)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (game_id) DO UPDATE
SET game_date = EXCLUDED.game_date,
    home_team = EXCLUDED.home_team,
    away_team = EXCLUDED.away_team,
    home_goals = EXCLUDED.home_goals,
    away_goals = EXCLUDED.away_goals,
    decided_in_ot_so = EXCLUDED.decided_in_ot_so; \
"""

def _fetch_day(d: date) -> list[dict]:
    r = requests.get(f"{BASE}/schedule/{d.isoformat()}", timeout=20)
    r.raise_for_status()
    data = r.json()
    games = []
    if isinstance(data, dict) and "gameWeek" in data:
        for blk in data.get("gameWeek", []):
            games.extend(blk.get("games", []))
    elif isinstance(data, dict) and isinstance(data.get("games"), list):
        games = data["games"]
    return games

def _is_final(g: dict) -> bool:
    # API typically exposes a status field; common values: FINAL, OFF, LIVE, PREVIEW
    s = (g.get("gameState") or g.get("gameStatus") or "").upper()
    return "FINAL" in s or s == "OFF"

def _extract_final_row(g: dict) -> tuple | None:
    if not _is_final(g):
        return None
    gid = g.get("id") or g.get("gameId")
    if not gid: return None
    try: gid = int(gid)
    except: return None
    
    home = (g.get("homeTeam") or {}).get("abbrev")
    away = (g.get("awayTeam") or {}).get("abbrev")
    if not home or not away: return None
    
    # Many schedule payloads carry "score" after final; if not, you can call a gamecenter endpoint.
    hg = (g.get("homeTeam") or {}).get("score")
    ag = (g.get("awayTeam") or {}).get("score")
    if hg is None or ag is None:
        return None  # skip if not present; small tweak: fetch per-game boxscore if you want
    
    ts = g.get("startTimeUTC") or ""
    game_date = ts.split("T", 1)[0] if "T" in ts else None
    
    decided_ot = bool((g.get("periodDescriptor") or {}).get("periodType") in ("OT","SO"))
    
    return (gid, game_date, home, away, int(hg), int(ag), decided_ot)

def main():
    start = date.today() - timedelta(days=14)
    #start = date(2024, 10, 8) # 2024-25 NHL season started Oct 8
    end   = date.today()   - timedelta(days=1)
    
    rows = []
    d = start
    while d <= end:
        for g in _fetch_day(d):
            row = _extract_final_row(g)
            if row: rows.append(row)
        d += timedelta(days=1)
        
    if not rows:
        log.info("No finished games found to upsert.")
        return
    
    with psycopg.connect(
        DATABASE_URL,
        sslmode="require",
        prefer_query_mode=None,
        prepare_threshold=None,
        prepared_statement_cache_queries=None,
    ) as conn, conn.cursor() as cur:
        execute_many(cur, SQL_UPSERT, rows)
        conn.commit()
    log.info("Upserted %d finished games into game_results.", len(rows))

if __name__ == "__main__":
    main()