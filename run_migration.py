"""
Database migration script for the Dollar Bot.
Run this script to set up the database schema in Supabase.

Usage: python run_migration.py
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv(".env.local")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

print("=" * 60)
print("Dollar Bot Database Migration")
print("=" * 60)
print()

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("Error: Missing environment variables.")
    print("Please set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
    sys.exit(1)

print(f"Target: {SUPABASE_URL}")
print()

# Read the SQL file
with open("migrations/001_initial_schema.sql", "r") as f:
    sql = f.read()

print("SQL migration file loaded successfully.")
print()

print("To run this migration:")
print()
print("1. Go to your Supabase dashboard:")
project_ref = SUPABASE_URL.replace("https://", "").replace(".supabase.co", "")
print(f"   https://supabase.com/dashboard/project/{project_ref}/sql/new")
print()
print("2. Open this repository file and copy its CONTENTS only:")
print("   migrations/000_complete_setup.sql")
print()
print("   Do not paste the filename or the text 'migrations/...'.")
print()
print("3. Click 'Run' once to execute the complete setup.")
print()
print("4. Verify channels, raw_posts, observations, market_snapshots, rate_history, and publish_targets exist in Table Editor.")
print()

# Try to verify connection
try:
    from supabase import create_client
    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    
    # Try to query the channels table
    result = client.table("channels").select("*").limit(1).execute()
    print("✓ Database connection verified!")
    print(f"  Found {len(result.data)} channel(s) in database.")
except Exception as e:
    print(f"⚠ Could not verify database: {str(e)[:100]}")
    print("  Please run the SQL migration manually in Supabase dashboard.")

print()
print("Migration was not executed by this workspace. Run migrations/000_complete_setup.sql in Supabase SQL Editor, then restart the service.")
