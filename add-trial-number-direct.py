#!/usr/bin/env python3
"""
Directly add trial number to database
"""

import asyncio
import asyncpg
import os
from pathlib import Path
from uuid import uuid4

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

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in .env")
    exit(1)

async def main():
    print("=" * 60)
    print("Adding Twilio Trial Number")
    print("=" * 60)
    print()

    trial_number = "+17372212163"
    trunk_id = "ST_Wp3ppL7yv8Zd"

    print(f"Number: {trial_number}")
    print(f"Trunk: {trunk_id}")
    print()

    print("Connecting to database...")
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Get first org
        org = await conn.fetchrow("SELECT id FROM organisations LIMIT 1")

        if not org:
            print("❌ No organization found!")
            print("   Please sign up first at http://localhost:3000")
            return

        org_id = org["id"]
        print(f"✓ Organization: {org_id}")
        print()

        # Check if exists
        existing = await conn.fetchrow("""
            SELECT id FROM telephony_numbers
            WHERE org_id = $1 AND phone_e164 = $2
        """, org_id, trial_number)

        if existing:
            print("Number exists, updating...")
            await conn.execute("""
                UPDATE telephony_numbers
                SET status = 'verified',
                    livekit_outbound_trunk_id = $1,
                    last_synced_at = NOW(),
                    last_error = NULL,
                    updated_at = NOW()
                WHERE id = $2
            """, trunk_id, existing["id"])
            result = existing
        else:
            print("Inserting new number...")
            number_id = uuid4()
            await conn.execute("""
                INSERT INTO telephony_numbers (
                    id, org_id, provider, phone_e164,
                    label, status, livekit_outbound_trunk_id,
                    last_synced_at, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), NOW(), NOW())
            """,
                number_id,
                org_id,
                "twilio",
                trial_number,
                "Trial Number (US)",
                "verified",
                trunk_id
            )
            result = {"id": number_id}

        print(f"✓ Number ready: {result['id']}")
        print()

        # Verify
        verify = await conn.fetchrow("""
            SELECT id, provider, phone_e164, label, status,
                   livekit_outbound_trunk_id
            FROM telephony_numbers
            WHERE phone_e164 = $1
        """, trial_number)

        print("Verification:")
        print(f"  ID: {verify['id']}")
        print(f"  Provider: {verify['provider']}")
        print(f"  Number: {verify['phone_e164']}")
        print(f"  Status: {verify['status']}")
        print(f"  Trunk: {verify['livekit_outbound_trunk_id']}")
        print()

        print("=" * 60)
        print("✅ Success!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("1. Refresh: http://localhost:3000/app/runs/new")
        print("2. Number should appear in dropdown!")
        print("3. Create voice agent (if needed)")
        print("4. Start test call to +918153083020")
        print()

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
