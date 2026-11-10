# pipelines/etl/ingest_historical.py
"""
One-time historical data loader for NHL game results.

This script fetches complete NHL seasons from the official NHL API and loads
them into the database. Run this once to backfill historical data, then use
the regular pipeline for ongoing updates.

Usage:
    # Load last 3 seasons
    python -m pipelines.etl.ingest_historical --seasons 3

    # Load specific seasons
    python -m pipelines.etl.ingest_historical --start-year 2021 --end-year 2024

    # Preview what would be loaded
    python -m pipelines.etl.ingest_historical --seasons 3 --dry-run
"""
from __future__ import annotations

import argparse
import logging
import time
from datetime import date, datetime, timedelta
from typing import List, Tuple
import requests
import psycopg

from pipelines.config import DATABASE_URL
from pipelines.common.db import connect, execute_many
from pipelines.common.logging_setup import setup as setup_logging

setup_logging("INFO")
log = logging.getLogger(__name__)

BASE = "https://api-web.nhle.com/v1"

# NHL season start/end dates (approximate)
SEASON_DATES = {
    2021: (date(2021, 10, 12), date(2022, 6, 26)),  # 2021-22
    2022: (date(2022, 10, 7), date(2023, 6, 13)),   # 2022-23
    2023: (date(2023, 10, 10), date(2024, 6, 24)),  # 2023-24
    2024: (date(2024, 10, 8), date(2025, 6, 30)),   # 2024-25
    2025: (date(2025, 10, 7), date(2026, 6, 29)),   # 2025-26 (in progress)
}

SQL_UPSERT_RESULTS = """
INSERT INTO game_results (game_id, game_date, home_team, away_team, home_goals, away_goals, decided_in_ot_so)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (game_id) DO UPDATE
SET game_date = EXCLUDED.game_date,
    home_team = EXCLUDED.home_team,
    away_team = EXCLUDED.away_team,
    home_goals = EXCLUDED.home_goals,
    away_goals = EXCLUDED.away_goals,
    decided_in_ot_so = EXCLUDED.decided_in_ot_so;
"""


def fetch_day_with_retry(d: date, max_retries: int = 3) -> list[dict]:
    """Fetch schedule for a single day with retry logic."""
    url = f"{BASE}/schedule/{d.isoformat()}"

    for attempt in range(max_retries):
        try:
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            data = r.json()

            games = []
            if isinstance(data, dict) and "gameWeek" in data:
                for blk in data.get("gameWeek", []):
                    games.extend(blk.get("games", []))
            elif isinstance(data, dict) and isinstance(data.get("games"), list):
                games = data["games"]

            return games

        except requests.RequestException as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt  # Exponential backoff
                log.warning(f"Failed to fetch {d} (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                log.error(f"Failed to fetch {d} after {max_retries} attempts: {e}")
                return []

    return []


def is_final(g: dict) -> bool:
    """Check if game is completed."""
    s = (g.get("gameState") or g.get("gameStatus") or "").upper()
    return "FINAL" in s or s == "OFF"


def extract_result_row(g: dict) -> Tuple | None:
    """Extract completed game result for database insertion."""
    if not is_final(g):
        return None

    gid = g.get("id") or g.get("gameId")
    if not gid:
        return None
    try:
        gid = int(gid)
    except:
        return None

    home = (g.get("homeTeam") or {}).get("abbrev")
    away = (g.get("awayTeam") or {}).get("abbrev")
    if not home or not away:
        return None

    hg = (g.get("homeTeam") or {}).get("score")
    ag = (g.get("awayTeam") or {}).get("score")
    if hg is None or ag is None:
        return None

    ts = g.get("startTimeUTC") or ""
    game_date = ts.split("T", 1)[0] if "T" in ts else None

    decided_ot = bool((g.get("periodDescriptor") or {}).get("periodType") in ("OT", "SO"))

    return (gid, game_date, home, away, int(hg), int(ag), decided_ot)


def fetch_season(start_date: date, end_date: date, season_name: str) -> List[Tuple]:
    """
    Fetch all completed games for a season.

    Args:
        start_date: Season start date
        end_date: Season end date (or today if season in progress)
        season_name: Human-readable season name for logging

    Returns:
        List of game result tuples
    """
    log.info("=" * 60)
    log.info(f"Fetching {season_name} season")
    log.info(f"Date range: {start_date} to {end_date}")
    log.info("=" * 60)

    # Don't fetch future dates
    if end_date > date.today():
        end_date = date.today()

    results = []
    current_date = start_date
    days_fetched = 0
    total_days = (end_date - start_date).days + 1

    while current_date <= end_date:
        days_fetched += 1

        # Progress indicator every 10 days
        if days_fetched % 10 == 0 or days_fetched == total_days:
            log.info(f"Progress: {days_fetched}/{total_days} days ({days_fetched * 100 // total_days}%)")

        # Fetch games for this day
        games = fetch_day_with_retry(current_date)

        # Extract completed games
        for g in games:
            row = extract_result_row(g)
            if row:
                results.append(row)

        current_date += timedelta(days=1)

        # Rate limiting - be nice to NHL API
        time.sleep(0.1)  # 100ms between requests

    log.info(f"Fetched {len(results)} completed games from {season_name}")
    return results


def load_seasons(start_year: int, end_year: int, dry_run: bool = False) -> dict:
    """
    Load multiple seasons of historical data.

    Args:
        start_year: First season year to load (e.g., 2021 for 2021-22 season)
        end_year: Last season year to load (e.g., 2024 for 2024-25 season)
        dry_run: If True, fetch data but don't write to database

    Returns:
        Dictionary with summary statistics
    """
    all_results = []
    seasons_loaded = []

    for year in range(start_year, end_year + 1):
        if year not in SEASON_DATES:
            log.warning(f"No date mapping for {year}-{year+1} season, skipping")
            continue

        season_start, season_end = SEASON_DATES[year]
        season_name = f"{year}-{str(year + 1)[2:]}"  # e.g., "2021-22"

        season_results = fetch_season(season_start, season_end, season_name)
        all_results.extend(season_results)
        seasons_loaded.append(season_name)

    log.info("")
    log.info("=" * 60)
    log.info("FETCH SUMMARY")
    log.info("=" * 60)
    log.info(f"Seasons loaded: {', '.join(seasons_loaded)}")
    log.info(f"Total games fetched: {len(all_results)}")

    if dry_run:
        log.info("DRY RUN - Not writing to database")
        return {
            "seasons": seasons_loaded,
            "games_fetched": len(all_results),
            "games_written": 0,
        }

    # Write to database
    if all_results:
        log.info("Writing to database...")
        with connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                execute_many(cur, SQL_UPSERT_RESULTS, all_results)
            conn.commit()
        log.info(f"Successfully wrote {len(all_results)} games to game_results table")
    else:
        log.warning("No games to write")

    log.info("=" * 60)

    return {
        "seasons": seasons_loaded,
        "games_fetched": len(all_results),
        "games_written": len(all_results),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Load historical NHL game results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Load last 3 seasons (recommended for initial setup)
  python -m pipelines.etl.ingest_historical --seasons 3

  # Load specific season range
  python -m pipelines.etl.ingest_historical --start-year 2021 --end-year 2023

  # Preview what would be loaded (doesn't write to DB)
  python -m pipelines.etl.ingest_historical --seasons 2 --dry-run

  # Load just current season
  python -m pipelines.etl.ingest_historical --start-year 2024 --end-year 2024
        """,
    )

    parser.add_argument(
        "--seasons",
        type=int,
        help="Number of recent seasons to load (e.g., 3 for last 3 seasons)",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        help="First season year to load (e.g., 2021 for 2021-22 season)",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        help="Last season year to load (e.g., 2024 for 2024-25 season)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch data but don't write to database",
    )

    args = parser.parse_args()

    # Determine year range
    current_season_year = date.today().year
    if date.today().month < 8:  # If before August, we're in the prior season
        current_season_year -= 1

    if args.seasons:
        end_year = current_season_year
        start_year = end_year - args.seasons + 1
    elif args.start_year and args.end_year:
        start_year = args.start_year
        end_year = args.end_year
    elif args.start_year:
        start_year = args.start_year
        end_year = current_season_year
    else:
        # Default: load last 3 seasons
        log.info("No season range specified, defaulting to last 3 seasons")
        end_year = current_season_year
        start_year = end_year - 2

    log.info(f"Loading seasons {start_year}-{start_year+1} through {end_year}-{end_year+1}")

    if args.dry_run:
        log.warning("DRY RUN MODE - Data will be fetched but not written to database")

    # Load the data
    summary = load_seasons(start_year, end_year, dry_run=args.dry_run)

    log.info("")
    log.info("Historical data load complete!")
    log.info(f"Seasons: {summary['seasons']}")
    log.info(f"Games fetched: {summary['games_fetched']}")
    log.info(f"Games written: {summary['games_written']}")


if __name__ == "__main__":
    main()
