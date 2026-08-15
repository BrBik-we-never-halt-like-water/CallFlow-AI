"""The `SpeechToText` and `TextToSpeech` protocols every STT/TTS adapter conforms to.

Only one vendor (Sarvam) has a real adapter today (`sarvam.py`) - see
`integrations/voice/protocol.py` for the precedent this file follows and the
reasoning behind it: keep the shape narrow until a second implementation
exists to prove it, and declare capabilities rather than assume every
provider implements everything (CLAUDE.md's Interface Segregation - prefer
`supports(capability)` over one fat interface every adapter must implement
fully).

Both protocols are structural `Protocol`s: an adapter conforms by having the
right methods, not by inheriting from anything here. A single adapter class
may implement both (Sarvam does - one vendor, two capabilities).
"""

from __future__ import annotations

from enum import Enum
from typing import Protocol


class AdapterUnavailable(RuntimeError):
    """Raised by an adapter method that can't currently do what's asked - a
    vendor HTTP error, a timeout, or a capability not actually implemented.
    Callers (the preview service) catch this and turn it into an honest
    "not available" result; it must never bubble up as an unhandled 500."""


class SttCapability(str, Enum):
    ONE_SHOT = (
        "one_shot"  # a single audio clip in, a transcript out - what a preview needs
    )
    STREAMING = (
        "streaming"  # real-time recognition - not exercised by anything in this task
    )


class SpeechToText(Protocol):
    def supports(self, capability: SttCapability) -> bool: ...

    async def transcribe_sample(
        self, *, api_key: str, audio_base64: str, language: str | None = None
    ) -> str: ...


class TtsCapability(str, Enum):
    ONE_SHOT = "one_shot"


class TextToSpeech(Protocol):
    def supports(self, capability: TtsCapability) -> bool: ...

    async def synthesize_sample(
        self, *, api_key: str, text: str, voice_id: str | None = None
    ) -> str:
        """Returns base64-encoded audio (wav or mp3, adapter's choice, documented per adapter)."""
        ...


__all__ = [
    "AdapterUnavailable",
    "SpeechToText",
    "SttCapability",
    "TextToSpeech",
    "TtsCapability",
]
