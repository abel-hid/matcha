"""
Every query below uses %s placeholders with parameters passed as a tuple —
never string formatting — so this is not vulnerable to SQL injection.
"""
import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

from app.config import Config

_pool = None


def init_pool(database_url=None):
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1, maxconn=20, dsn=database_url or Config.DATABASE_URL
        )
    return _pool


@contextmanager
def get_conn():
    p = init_pool()
    conn = p.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        p.putconn(conn)


def query_one(sql, params=None):
    """SELECT expected to return 0 or 1 row. Returns a dict or None."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params or ())
            row = cur.fetchone()
            return dict(row) if row else None


def query_all(sql, params=None):
    """SELECT expected to return 0+ rows. Returns a list of dicts."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params or ())
            return [dict(r) for r in cur.fetchall()]


def execute(sql, params=None, returning=False):
    """INSERT/UPDATE/DELETE. Pass returning=True with a RETURNING clause
    to get the affected row back as a dict; otherwise returns rowcount."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params or ())
            if returning:
                row = cur.fetchone()
                return dict(row) if row else None
            return cur.rowcount
