# pipelines/pricing/compute_team_elos.py
from __future__ import annotations
import psycopg
from decimal import Decimal, getcontext
from pipelines.config import DATABASE_URL
from pipelines.common.db import connect, execute_one  # <- use your helper that injects prepare_threshold=0
from pipelines.common.logging_setup import setup as setup_logging

setup_logging("INFO")
getcontext().prec = 28

K = Decimal("10")            # update strength (slower learning = more stable)
H = Decimal("50")            # home-ice Elo boost (stronger home advantage)

def _expected(elo_a: Decimal, elo_b: Decimal) -> Decimal:
    # Bradley–Terry via Elo logistic
    diff = (elo_a - elo_b) / Decimal("400")
    ten = Decimal("10") ** diff
    return ten / (Decimal("1") + ten)

def main():
    with connect(DATABASE_URL,
        sslmode="require",
        prefer_query_mode=None,
        prepare_threshold=None,
        prepared_statement_cache_queries=None,
    ) as conn:
        with conn.cursor() as cur:
            # grab finished games not yet trained
            execute_one(cur,"""
              SELECT r.game_id, r.home_team, r.away_team, r.home_goals, r.away_goals
              FROM game_results r
              LEFT JOIN elo_training_ledger l ON l.game_id = r.game_id
              WHERE l.game_id IS NULL
              ORDER BY r.game_date, r.game_id
            """)
            games = cur.fetchall()
            if not games:
                print("Elo: No new finished games to train.")
                return
        
            # load current elos
            execute_one(cur,"SELECT team_abbr, elo FROM team_ratings")
            elo = {abbr: Decimal(str(e)) for (abbr, e) in cur.fetchall()}
        
            for gid, home, away, hg, ag, in games:
                eh = elo.get(home, Decimal("1500"))
                ea = elo.get(away, Decimal("1500"))
            
                # expected with home-ice
                ph = _expected(eh + H, ea) # expected home win prob
                ah = Decimal("1.0") if hg > ag else Decimal("0.0")
                # (tie handling: NHL has OT/SO, but winner exists; if you later model 3-way, adapt here)
            
                # update
                eh_new = eh + K * (ah - ph)
                ea_new = ea + K * ((Decimal("1.0") - ah) - (Decimal("1.0") - ph))
            
                elo[home] = eh_new
                elo[away] = ea_new
            
                # ledger mark
                execute_one(cur,"INSERT INTO elo_training_ledger (game_id) VALUES (%s) ON CONFLICT DO NOTHING", (gid,))
            
            # write updated elos
            for team, val in elo.items():
                execute_one(cur,"""
                  INSERT INTO team_ratings (team_abbr, elo, updated_at)
                  VALUES (%s, %s, now())
                  ON CONFLICT (team_abbr) DO UPDATE
                  SET elo = EXCLUDED.elo, updated_at = now()
                """, (team, val))
            
            conn.commit()
            print(f"elo: trained on {len(games)} games and updated team_ratings.")

if __name__ == "__main__":
    main()