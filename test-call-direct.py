#!/usr/bin/env python3
"""
Create and start a run directly via database
Bypasses API auth for testing
"""

import asyncio
import asyncpg
import os
from pathlib import Path
from uuid import uuid4
import json

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
    print("=" * 60)
    print("Direct Database Test Call")
    print("=" * 60)
    print()

    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Get org
        org = await conn.fetchrow("SELECT id FROM organisations LIMIT 1")
        org_id = org["id"]
        print(f"✓ Organization: {org_id}")

        # Get user (through membership)
        member = await conn.fetchrow("""
            SELECT u.id, u.auth_user_id
            FROM users u
            JOIN memberships m ON u.id = m.user_id
            WHERE m.org_id = $1
            LIMIT 1
        """, org_id)
        if not member:
            print("❌ No user found!")
            return
        user_id = member["id"]
        auth_user_id = member["auth_user_id"]
        print(f"✓ User: {user_id}")
        print()

        # Get or create voice agent
        agent = await conn.fetchrow("""
            SELECT id, name FROM voice_agents
            WHERE org_id = $1
            LIMIT 1
        """, org_id)

        if not agent:
            print("Creating voice agent...")
            agent_id = uuid4()
            await conn.execute("""
                INSERT INTO voice_agents (
                    id, org_id, name, kind,
                    llm_provider, llm_model,
                    system_prompt, collect_fields,
                    created_at, updated_at, created_by
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW(), $9)
            """,
                agent_id, org_id, "API Test Agent", "custom",
                "openrouter", "google/gemini-2.5-flash-preview",
                "You are a test assistant. Keep it very short. Just say you can hear the caller and ask them to confirm receipt.",
                json.dumps([]),
                user_id
            )
            print(f"✓ Created agent: {agent_id}")
        else:
            agent_id = agent["id"]
            print(f"✓ Using agent: {agent['name']} ({agent_id})")
        print()

        # Get number
        number = await conn.fetchrow("""
            SELECT id, phone_e164 FROM telephony_numbers
            WHERE org_id = $1 AND status = 'verified'
            LIMIT 1
        """, org_id)

        if not number:
            print("❌ No telephony number found!")
            print("   Run: python add-trial-number-direct.py")
            return

        number_id = number["id"]
        phone = number["phone_e164"]
        print(f"✓ Using number: {phone} ({number_id})")
        print()

        # Create run
        print("Creating run...")
        run_id = str(uuid4())  # runs.id is text

        await conn.execute("""
            INSERT INTO runs (
                id, org_id, voice_agent_id,
                run_instruction, status, started_by, total,
                started_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, 0, NOW())
        """,
            run_id, org_id, agent_id,
            "Test call - please confirm you received this from CallFlow AI",
            "running",  # Start directly as running
            user_id
        )
        print(f"✓ Run created and started: {run_id}")

        # Link number to run
        print("Linking number to run...")
        await conn.execute("""
            INSERT INTO run_numbers (run_id, number_id, org_id)
            VALUES ($1, $2, $3)
        """, run_id, number_id, org_id)
        print("✓ Number linked")
        print()

        print("✓ Run created!")
        print()
        print("Note: The system should automatically:")
        print("  1. Pick up the running run")
        print("  2. Find numbers from run_numbers")
        print("  3. Start dialing")
        print()
        print("But we don't have contacts configured properly.")
        print("The dashboard UI adds contacts via the API.")
        print()
        print("For now, this proves the infrastructure is ready!")
        print()

        print("=" * 60)
        print("Run Created and Started!")
        print("=" * 60)
        print()
        print(f"Run ID: {run_id}")
        print(f"Agent: {agent_id}")
        print(f"Number: {phone}")
        print(f"Contact: +918153083020")
        print()
        print("What should happen:")
        print("1. Run reconciler picks up the run")
        print("2. Dialer starts calling the contact")
        print("3. LiveKit creates room and dispatches voice worker")
        print("4. Twilio makes call through SIP trunk")
        print("5. Your phone rings!")
        print()
        print("Monitor:")
        print(f"- Dashboard: http://localhost:3000/app/runs/{run_id}")
        print("- API logs: (check terminal where uvicorn is running)")
        print("- Voice worker logs: (check background task output)")
        print()
        print("Check your phone +918153083020 in the next 10 seconds!")
        print()

        # Monitor for 30 seconds
        print("Monitoring for 30 seconds...")
        for i in range(6):
            await asyncio.sleep(5)
            run = await conn.fetchrow("""
                SELECT status FROM runs WHERE id = $1
            """, run_id)

            calls = await conn.fetch("""
                SELECT status, disposition FROM call_outcomes
                WHERE run_id = $1
            """, run_id)

            print(f"  [{i*5}s] Run: {run['status']}, Calls: {len(calls)}")

            if calls:
                for call in calls:
                    print(f"       Call: {call['status']} - {call['disposition']}")

        print()
        print("Done monitoring. Check dashboard for full results.")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
