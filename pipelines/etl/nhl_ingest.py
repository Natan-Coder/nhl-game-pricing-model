import os
import psycopg
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

from pipelines.config import DATABASE_URL

here = Path(__file__).resolve()
for p in [here.parents[1] / ".env", here.parents[2] / "shared/config/.env"]:
    if p.exists():
        load_dotenv(p, override=False)
        

UPSERT_FEATURES = """
INSERT INTO game_features (game_id, game_date, home_team, away_team, home_rest, away_rest, home_back_to_back, away_back_to_back, home_elo, away_elo)
VALUES (%(game_id)s, %(game_date)s, %(home_team)s, %(away_team)s, %(home_rest)s, %(away_rest)s, %(home_b2b)s, %(away_b2b)s, %(home_elo)s, %(away_elo)s)
ON CONFLICT (game_id) DO UPDATE SET game_date=EXCLUDED.game_date, home_team=EXCLUDED.home_team, away_team=EXCLUDED.away_team; \
"""


UPSERT_PRICING = """
INSERT INTO game_pricing (game_id, p_home_win, p_away_win, total_lambda)
VALUES (%(game_id)s, %(p_home)s, %(p_away)s, %(lambda)s)
ON CONFLICT (game_id) DO UPDATE SET p_home_win=EXCLUDED.p_home_win, p_away_win=EXCLUDED.p_away_win, total_lambda=EXCLUDED.total_lambda; \
"""


# TODO: Replace with actual NHL API pull & feature calc

def demo_ingest() -> None:
    sample = {
        "game_id": 2025010102,
        "game_date": date.today(),
        "home_team": "NYR",
        "away_team": "NJD",
        "home_rest": 2,
        "away_rest": 1,
        "home_b2b": False,
        "away_b2b": False,
        "home_elo": 1520,
        "away_elo": 1510,
        "p_home": 0.53,
        "p_away": 0.47,
        "lambda": 6.0,
    }
    with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute(UPSERT_FEATURES, sample)
        cur.execute(UPSERT_PRICING, sample)
        conn.commit()
        print("Demo ingest done.")


if __name__ == "__main__":
    demo_ingest()