# The voice runtime, for local development only.
#
# `VOICE_EXTRAS` picks which vendor plugins are installed - the same list the
# deploy uses, so a plugin missing here is a plugin missing in production too.
# Each `livekit-plugins-*` pulls a substantial tree, which is exactly why it is
# a build argument rather than "install everything".
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# `livekit-agents` needs ffmpeg for audio, and silero's VAD runs on onnxruntime,
# which links against libgomp.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential ffmpeg libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/apps/voice-runtime

ARG VOICE_EXTRAS=sarvam,openai,silero
COPY apps/voice-runtime/pyproject.toml ./
RUN pip install --no-cache-dir -e ".[${VOICE_EXTRAS},dev]"

COPY apps/voice-runtime ./

# The worker's own health endpoint, which pm2 and compose both use to tell
# "registered with LiveKit" from "process is alive".
EXPOSE 8081
CMD ["python", "-m", "app.worker", "start"]
