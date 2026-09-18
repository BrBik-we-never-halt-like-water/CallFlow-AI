#!/usr/bin/env python3
"""
Check database schema for testing
"""

import asyncio
import asyncpg
import os
from pathlib import Path

# Load .env
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key] = value

DATABASE_URL = os.getenv("DATABASE_URL")

async def main():
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        print("=" * 60)
        print("Database Schema Check")
        print("=" * 60)
        print()

        # Check runs table columns
        print("1. RUNS TABLE COLUMNS:")
        columns = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'runs'
            ORDER BY ordinal_position
        """)
        for col in columns:
            print(f"   - {col['column_name']}: {col['data_type']}")
        print()

        # Check voice_agents table columns
        print("2. VOICE_AGENTS TABLE COLUMNS:")
        columns = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'voice_agents'
            ORDER BY ordinal_position
        """)
        for col in columns:
            print(f"   - {col['column_name']}: {col['data_type']}")
        print()

        # Check telephony_numbers
        print("3. TELEPHONY_NUMBERS:")
        numbers = await conn.fetch("""
            SELECT id, phone_e164, status, livekit_outbound_trunk_id
            FROM telephony_numbers
        """)
        for num in numbers:
            print(f"   - {num['phone_e164']}: {num['status']}, trunk={num['livekit_outbound_trunk_id']}")
        print()

        # Check voice_agents
        print("4. VOICE_AGENTS:")
        agents = await conn.fetch("""
            SELECT id, name
            FROM voice_agents
        """)
        for agent in agents:
            print(f"   - {agent['name']}: {agent['id']}")
        print()

        # Check run_numbers table if exists
        print("5. RUN_NUMBERS TABLE (if exists):")
        try:
            columns = await conn.fetch("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'run_numbers'
            """)
            for col in columns:
                print(f"   - {col['column_name']}")
        except:
            print("   (table does not exist)")
        print()

        print("=" * 60)

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
