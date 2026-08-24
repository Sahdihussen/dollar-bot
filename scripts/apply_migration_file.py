"""Apply a single SQL migration file via the Supabase Postgres connection string.

Usage: python3 scripts/apply_migration_file.py migrations/009_pending_actions.sql

Requires DATABASE_URL (the Supabase Postgres connection string) in the
workspace environment (.env.local or Settings → Environment).
If it is not configured, the script prints instructions for the SQL editor.
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv(".env.local")

url = os.getenv("DATABASE_URL", "").strip()
if not url:
    print("DATABASE_URL is not configured.")
    print("Either add the Supabase Postgres connection string, or run the SQL")
    print("manually in the Supabase dashboard SQL editor (see the file contents).")
    sys.exit(2)

sql_path = sys.argv[1] if len(sys.argv) > 1 else ""
if not sql_path:
    print("Usage: python3 scripts/apply_migration_file.py migrations/<file>.sql")
    sys.exit(2)

try:
    import psycopg
except ImportError:
    print("The PostgreSQL driver is not installed. Install psycopg[binary] first.")
    sys.exit(3)

with open(sql_path, "r", encoding="utf-8") as migration_file:
    sql = migration_file.read()

try:
    with psycopg.connect(url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)
        connection.commit()
    print(f"Migration applied successfully: {sql_path}")
except Exception as exc:
    print(f"Migration failed: {type(exc).__name__}: {exc}")
    sys.exit(1)
