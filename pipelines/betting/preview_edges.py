"""Preview actionable edges for upcoming games."""
import psycopg
from pipelines.config import DATABASE_URL
from decimal import Decimal

with psycopg.connect(DATABASE_URL) as conn:
    with conn.cursor() as cur:
        cur.execute('''
            SELECT
                gf.home_team || ' vs ' || gf.away_team as matchup,
                TO_CHAR(gf.game_datetime_utc AT TIME ZONE 'America/New_York', 'Mon DD HH12:MI AM') as game_time,
                e.book,
                e.market,
                e.outcome,
                e.american_odds,
                e.model_prob,
                e.implied_prob,
                e.edge,
                e.kelly_fraction,
                e.suggested_stake
            FROM edges e
            JOIN game_features gf ON e.game_id = gf.game_id
            WHERE gf.game_date >= CURRENT_DATE
              AND gf.game_datetime_utc > NOW() + INTERVAL '2 hours'
              AND e.edge >= 0.03
              AND e.market = 'moneyline'
            ORDER BY e.edge DESC
            LIMIT 20
        ''')

        rows = cur.fetchall()

        if not rows:
            print('No actionable edges found (min 3% edge)')
        else:
            print('='*120)
            print('TOP ACTIONABLE EDGES (Min 3% Edge, Moneyline Only)')
            print('='*120)
            header = f"{'Game':<25} {'Time':<15} {'Book':<12} {'Bet':<8} {'Odds':<7} {'Model':<7} {'Implied':<8} {'Edge':<7} {'Kelly%':<8} {'Stake':<7}"
            print(header)
            print('-'*120)

            for row in rows:
                matchup, game_time, book, market, outcome, odds, model_prob, implied_prob, edge, kelly, stake = row
                line = f"{matchup:<25} {game_time:<15} {book:<12} {outcome:<8} {odds:+6} {float(model_prob)*100:6.1f}% {float(implied_prob)*100:7.1f}% {float(edge)*100:6.1f}% {float(kelly)*100:7.2f}% ${float(stake):6.2f}"
                print(line)

            print('='*120)
            print(f'Total edges found: {len(rows)}')
            print('='*120)
