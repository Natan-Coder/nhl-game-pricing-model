# pipelines/common/db.py
from __future__ import annotations
from contextlib import contextmanager
import psycopg
import logging

log = logging.getLogger(__name__)

@contextmanager
def connect(dsn: str, **kwargs):
    """
    Connect to the database with optional connection parameters.
    Always sets prepare_threshold=None unless explicitly overridden.
    """
    conn_params = {"prepare_threshold": None}
    conn_params.update(kwargs)
    conn = psycopg.connect(dsn, **conn_params)
    try:
        yield conn
    finally:
        conn.close()

def execute_one(cur, sql: str, params: tuple | None = None):
    # For DDL / ad-hoc statements where we don’t want prepared statements:
    cur.execute(sql, params or (), prepare=False)
    return cur.rowcount or 0


def execute_many(cur, sql: str, rows: list[tuple], chunk: int = 500):
    """
    Bulk insert/update in chunks. Do NOT pass prepare= here; psycopg executemany()
    has no such kwarg. Chunking helps avoid large parameter lists.
    """
    if not rows:
        return 0
    total = 0
    for i in range(0, len(rows), chunk):
        batch = rows[i:i+chunk]
        cur.executemany(sql, batch)  # no prepare kwarg!
        total += cur.rowcount or 0
    return total