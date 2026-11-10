import psycopg, logging
from pipelines.config import DATABASE_URL

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def main():
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("REFRESH MATERIALIZED VIEW mv_best_moneyline;")
        conn.commit()
    logging.info("Refreshed mv_best_moneyline")

if __name__ == "__main__":
    main()
