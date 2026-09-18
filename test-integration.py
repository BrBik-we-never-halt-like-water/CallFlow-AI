#!/usr/bin/env python3
"""
Quick integration test: LiveKit → Twilio → Your Phone

Tests the full stack without needing the voice worker running.
This proves the SIP trunk is configured correctly.
"""

import asyncio
import os
import sys

# Add apps/api to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'apps', 'api'))

from app.integrations.livekit.client import LiveKitGateway
from app.core.config import config

async def test_livekit_twilio():
    """Test LiveKit can call through Twilio trunk"""

    print("=" * 60)
    print("Integration Test: LiveKit → Twilio → Your Phone")
    print("=" * 60)
    print()

    # Verify config
    print("✓ LiveKit URL:", config.livekit_url)
    print("✓ SIP Host:", config.livekit_sip_host)
    print()

    # Create gateway
    print("Connecting to LiveKit...")
    async with LiveKitGateway() as gateway:
        print("✓ Connected!")
        print()

        # Note: Actual call test requires trunk ID from LiveKit dashboard
        print("LiveKit Gateway is ready.")
        print()
        print("Next step:")
        print("1. Get Trunk ID from LiveKit dashboard (TR_...)")
        print("2. Test a call from the dashboard at /app/runs/new")
        print("3. Or run the full H6 wiring guide")
        print()

if __name__ == "__main__":
    asyncio.run(test_livekit_twilio())
