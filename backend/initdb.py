"""
Apply schema.sql to the configured PostgreSQL database.

Run without deleting data:

    python initdb.py

Recreate the public schema and delete all existing data:

    python initdb.py --reset
"""
import argparse
from pathlib import Path

import psycopg2

from app.config import Config

BASE_DIR = Path(__file__).resolve().parent
SCHEMA_FILE = BASE_DIR / 'schema.sql'


def parse_arguments():
    """Parse the explicit destructive-reset option for schema setup."""
    parser = argparse.ArgumentParser(description='Apply the Matcha database schema.')
    parser.add_argument(
        '--reset',
        action='store_true',
        help='drop and recreate the public schema before applying schema.sql',
    )
    return parser.parse_args()


def apply_schema(reset=False):
    """Optionally reset the public schema and apply schema.sql atomically."""
    Config.validate_database()
    schema_sql = SCHEMA_FILE.read_text(encoding='utf-8')

    conn = psycopg2.connect(Config.DATABASE_URL)
    try:
        with conn.cursor() as cur:
            if reset:
                print('Reset requested: all existing database data will be deleted.')
                cur.execute('DROP SCHEMA public CASCADE')
                cur.execute('CREATE SCHEMA public')

            cur.execute(schema_sql)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    if reset:
        print('Database reset and schema applied successfully.')
    else:
        print('Schema applied successfully.')


if __name__ == '__main__':
    args = parse_arguments()
    apply_schema(reset=args.reset)
