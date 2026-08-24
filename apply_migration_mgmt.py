"""Apply migrations/000_complete_setup.sql via the Supabase Management API.

Requires SUPABASE_ACCESS_TOKEN (personal access token from
https://supabase.com/dashboard/account/tokens) in the environment.
The token and response bodies are never printed.
"""
import os
import sys

import httpx

from dotenv import load_dotenv

load_dotenv(".env.local")

PROJECT_REF = os.getenv("SUPABASE_URL", "").replace("https://", "").replace(".supabase.co", "")
TOKEN = os.getenv("SUPABASE_ACCESS_TOKEN", "").strip()

if not TOKEN:
    print("SUPABASE_ACCESS_TOKEN is not configured.")
    print("Create one at https://supabase.com/dashboard/account/tokens and add it in Freebuff Settings → Environment.")
    sys.exit(2)

if not PROJECT_REF:
    print("SUPABASE_URL is not configured.")
    sys.exit(2)

ENDPOINT = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}


def run_query(query: str) -> None:
    with httpx.Client(timeout=120.0) as client:
        response = client.post(ENDPOINT, headers=HEADERS, json={"query": query})
    if response.status_code >= 400:
        print(f"Query failed (HTTP {response.status_code}).")
        print(response.text[:2000])
        sys.exit(1)


sql_path = sys.argv[1] if len(sys.argv) > 1 else "migrations/000_complete_setup.sql"
with open(sql_path, "r", encoding="utf-8") as migration_file:
    sql = migration_file.read()

print("Verifying access token...")
try:
    run_query("select 1")
except SystemExit:
    print("Access token was rejected or the project ref is wrong.")
    sys.exit(1)

print("Applying migration...")
run_query(sql)
print("Migration applied successfully.")
