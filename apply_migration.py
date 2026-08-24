"""Apply migrations/000_complete_setup.sql using DATABASE_URL.

This is intentionally separate from the application. Set DATABASE_URL in the
workspace environment, then run: python3 apply_migration.py
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv(".env.local")

url = os.getenv("DATABASE_URL", "").strip()
if not url:
    print("DATABASE_URL is not configured.")
    print("Add the Supabase Postgres connection string in Freebuff Settings → Environment, then run this script again.")
    sys.exit(2)

try:
    import psycopg
except ImportError:
    print("The PostgreSQL driver is not installed. Install psycopg[binary] first.")
    sys.exit(3)

sql_path = "migrations/000_complete_setup.sql"
with open(sql_path, "r", encoding="utf-8") as migration_file:
    sql = migration_file.read()

try:
    with psycopg.connect(url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)
        connection.commit()
    print("Migration applied successfully.")
except Exception as exc:
    print(f"Migration failed: {type(exc).__name__}: {exc}")
    sys.exit(1)
