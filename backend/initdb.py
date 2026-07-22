"""
Replaces `flask db upgrade`. Run once to create tables:

    python init_db.py
"""
import psycopg2
from app.config import Config

with open('schema.sql', 'r') as f:
    schema_sql = f.read()

conn = psycopg2.connect(Config.DATABASE_URL)
try:
    with conn.cursor() as cur:
        cur.execute(schema_sql)
    conn.commit()
    print("Schema applied successfully.")
finally:
    conn.close()