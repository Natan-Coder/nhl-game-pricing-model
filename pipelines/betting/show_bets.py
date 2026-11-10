# pipelines/betting/show_bets.py
"""
Quick utility to view active (pending) bets.
Run: vpy -m pipelines.betting.show_bets
"""
from __future__ import annotations
from datetime import timezone
import logging
import psycopg
import pytz


from pipelines.config import DATABASE_URL
from pipelines.common.logging_setup import setup as setup_logging

setup_logging("INFO")
log = logging.getLogger(__name__)


def show_active_bets():
    """Display all pending bets with details."""
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # Get all pending bets
            cur.execute("""
                SELECT
                    b.bet_id,
                    bs.strategy_name,
                    gf.home_team || ' vs ' || gf.away_team as matchup,
                    TO_CHAR(gf.game_datetime_utc AT TIME ZONE 'America/New_York', 'Mon DD HH12:MI AM') as game_time,
                    b.book,
                    b.market,
                    b.outcome,
                    b.american_odds,
                    b.stake,
                    b.edge,
                    b.is_parlay,
                    b.parlay_id
                FROM bet_log b
                JOIN betting_strategies bs ON b.strategy_id = bs.strategy_id
                JOIN game_features gf ON b.game_id = gf.game_id
                WHERE b.bet_status = 'pending'
                ORDER BY gf.game_datetime_utc, b.bet_id
            """)

            rows = cur.fetchall()

            if not rows:
                log.info("No active bets")
                return

            # Display bets
            log.info("=" * 100)
            log.info(f"Active Bets ({len(rows)} total)")
            log.info("=" * 100)

            for row in rows:
                bet_id, strategy, matchup, game_time, book, market, outcome, odds, stake, edge, is_parlay, parlay_id = row

                parlay_flag = f" [PARLAY #{parlay_id}]" if is_parlay else ""

                log.info(f"Bet #{bet_id:3} | {strategy:20} | {matchup:20} | {game_time}")
                log.info(f"         {book:15} {market:10} {outcome:10} {odds:+5} | "
                        f"Stake: ${stake:6.2f} | Edge: {edge:5.1%}{parlay_flag}")
                log.info("")

            # Show summary by strategy
            cur.execute("""
                SELECT
                    bs.strategy_name,
                    COUNT(*) as num_bets,
                    SUM(b.stake) as total_stake
                FROM bet_log b
                JOIN betting_strategies bs ON b.strategy_id = bs.strategy_id
                WHERE b.bet_status = 'pending'
                GROUP BY bs.strategy_name
                ORDER BY total_stake DESC
            """)

            summary_rows = cur.fetchall()

            log.info("=" * 100)
            log.info("Summary by Strategy:")
            for name, count, total in summary_rows:
                log.info(f"  {name:30} {count:2} bets  ${total:7.2f}")

            # Show overall totals
            total_bets = sum(row[1] for row in summary_rows)
            total_stake = sum(row[2] for row in summary_rows)

            log.info("")
            log.info(f"Total: {total_bets} bets, ${total_stake:.2f} stake")
            log.info("=" * 100)


def main():
    """Main entry point."""
    show_active_bets()


if __name__ == "__main__":
    main()
