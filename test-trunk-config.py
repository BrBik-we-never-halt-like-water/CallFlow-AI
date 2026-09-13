#!/usr/bin/env python3
"""Quick test: Verify trunk configuration is ready"""

import os
from pathlib import Path

print("=" * 60)
print("Trunk Configuration Test")
print("=" * 60)
print()

# Load .env
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key] = value

# Check required values
required = {
    "LIVEKIT_URL": os.getenv("LIVEKIT_URL"),
    "LIVEKIT_API_KEY": os.getenv("LIVEKIT_API_KEY"),
    "LIVEKIT_API_SECRET": os.getenv("LIVEKIT_API_SECRET"),
    "LIVEKIT_SIP_HOST": os.getenv("LIVEKIT_SIP_HOST"),
    "LIVEKIT_SIP_TRUNK_ID": os.getenv("LIVEKIT_SIP_TRUNK_ID"),
}

missing = []
for key, value in required.items():
    if value:
        if "SECRET" in key or "KEY" in key:
            display = value[:8] + "..." if len(value) > 8 else value
        else:
            display = value
        print(f"✓ {key}: {display}")
    else:
        print(f"✗ {key}: NOT SET")
        missing.append(key)

print()

if missing:
    print(f"❌ Missing: {', '.join(missing)}")
    exit(1)

print("✅ All trunk configuration values present!")
print()
print("Trunk Details:")
print(f"  - Trunk ID: {os.getenv('LIVEKIT_SIP_TRUNK_ID')}")
print(f"  - SIP Host: {os.getenv('LIVEKIT_SIP_HOST')}")
print()
print("Next step: Configure Twilio inbound routing")
print(f"  URL: https://{os.getenv('LIVEKIT_SIP_HOST')}")
