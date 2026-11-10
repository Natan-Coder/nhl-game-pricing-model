# pipelines/config.py
import os
from pathlib import Path
from dotenv import load_dotenv



def _load_env():
    # 1) pipelines/.env  2) shared/config/.env (optional fallback)
    for p in [
        Path(__file__).resolve().parent / ".env",
        Path(__file__).resolve().parents[1] / "shared" / "config" / ".env",
    ]:
        if p.exists():
            load_dotenv(p, override=True)

_load_env()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("Set DATABASE_URL in pipelines/.env (or shared/config/.env)")

BANKROLL = float(os.getenv("BANKROLL", "1000"))

# Alert configuration
ALERT_MIN_EDGE = float(os.getenv("ALERT_MIN_EDGE", "0.03"))      # 3% minimum edge
ALERT_MIN_KELLY = float(os.getenv("ALERT_MIN_KELLY", "0.015"))   # 1.5% minimum Kelly
ALERT_MIN_STAKE = float(os.getenv("ALERT_MIN_STAKE", "5.00"))    # $5 minimum stake