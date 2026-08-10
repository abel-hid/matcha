import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

from app.config import Config

_pool = None


def init_pool(database_url=None, minimum=None, maximum=None):
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=minimum or Config.DB_POOL_MIN,
            maxconn=maximum or Config.DB_POOL_MAX,
            dsn=database_url or Config.DATABASE_URL,
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


def query_one(sql, params=None): # SELECT expected to return 0 or 1 row.
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params or ())
            row = cur.fetchone()
            return dict(row) if row else None


def query_all(sql, params=None): # SELECT expected to return 0 or more rows.
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params or ())
            return [dict(r) for r in cur.fetchall()]


def execute(sql, params=None, returning=False): #returning=False means we don't expect a result set, returning=True means we expect a single row to be returned.
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur: # Cursor factory allows us to get results as dictionaries instead of tuples.
            cur.execute(sql, params or ())
            if returning:
                row = cur.fetchone()
                return dict(row) if row else None
            return cur.rowcount
