"""Sarvam AI adapter: Bulbul (text-to-speech) and Saarika (speech-to-text).

Written against Sarvam's public REST API docs as researched on 2026-08-15:
  - TTS:  https://docs.sarvam.ai/api-reference/text-to-speech/convert
          https://docs.sarvam.ai/api-reference-docs/text-to-speech/api/rest-api
  - STT:  https://docs.sarvam.ai/api-reference-docs/speech-to-text/transcribe
          https://docs.sarvam.ai/api-reference-docs/api-guides-tutorials/speech-to-text/rest-api

This has **not** been exercised against a live Sarvam key in this
environment - none is configured here. If a real preview call fails once a
key is added, the first thing to check is whether the endpoint path, the
`api-subscription-key` header, or the request/response field names below
have drifted from what's documented above.

Bulbul's REST API already returns base64-encoded audio in a JSON field
(`audios[0]`), so `synthesize_sample` just extracts it - there is no raw
audio to re-encode ourselves. Saarika's REST API is `multipart/form-data`
(the file, not JSON), so `transcribe_sample` decodes the base64 it is given
back to raw bytes before uploading.
"""

from __future__ import annotations

import base64
import binascii

import httpx

from app.integrations.ai_providers.protocol import (
    AdapterUnavailable,
    SttCapability,
    TtsCapability,
)

_BASE_URL = "https://api.sarvam.ai"
_TTS_URL = f"{_BASE_URL}/text-to-speech"
_STT_URL = f"{_BASE_URL}/speech-to-text"
_TIMEOUT = httpx.Timeout(30.0)

_DEFAULT_TTS_MODEL = "bulbul:v2"
_DEFAULT_TTS_SPEAKER = "anushka"
_DEFAULT_TTS_LANGUAGE = "en-IN"
_DEFAULT_STT_MODEL = "saarika:v2.5"


class SarvamAdapter:
    """Implements both `SpeechToText` and `TextToSpeech` structurally - one
    vendor, two capabilities, so one adapter class covers both protocols."""

    def supports(self, capability: SttCapability | TtsCapability) -> bool:
        return capability in (SttCapability.ONE_SHOT, TtsCapability.ONE_SHOT)

    async def synthesize_sample(
        self, *, api_key: str, text: str, voice_id: str | None = None
    ) -> str:
        payload = {
            "text": text,
            "language_code": _DEFAULT_TTS_LANGUAGE,
            "speaker": voice_id or _DEFAULT_TTS_SPEAKER,
            "model": _DEFAULT_TTS_MODEL,
        }
        body = await self._post_json(
            _TTS_URL, headers={"api-subscription-key": api_key}, json=payload
        )
        audios = body.get("audios")
        if not audios:
            raise AdapterUnavailable(f"Sarvam TTS response had no audio: {body}")
        return audios[0]

    async def transcribe_sample(
        self, *, api_key: str, audio_base64: str, language: str | None = None
    ) -> str:
        try:
            audio_bytes = base64.b64decode(audio_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise AdapterUnavailable(
                f"Audio sample is not valid base64: {exc}"
            ) from exc

        data = {"model": _DEFAULT_STT_MODEL}
        if language:
            data["language_code"] = language
        files = {"file": ("sample.wav", audio_bytes, "audio/wav")}

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.post(
                    _STT_URL,
                    headers={"api-subscription-key": api_key},
                    data=data,
                    files=files,
                )
        except httpx.HTTPError as exc:
            raise AdapterUnavailable(f"Sarvam STT request failed: {exc}") from exc

        if response.status_code >= 400:
            raise AdapterUnavailable(
                f"Sarvam STT returned {response.status_code}: {response.text[:500]}"
            )

        transcript = response.json().get("transcript")
        if transcript is None:
            raise AdapterUnavailable(
                f"Sarvam STT response had no transcript: {response.text[:500]}"
            )
        return transcript

    async def _post_json(
        self, url: str, *, headers: dict[str, str], json: dict
    ) -> dict:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.post(
                    url,
                    headers={**headers, "Content-Type": "application/json"},
                    json=json,
                )
        except httpx.HTTPError as exc:
            raise AdapterUnavailable(f"Sarvam request to {url} failed: {exc}") from exc

        if response.status_code >= 400:
            raise AdapterUnavailable(
                f"Sarvam returned {response.status_code} from {url}: {response.text[:500]}"
            )
        return response.json()


__all__ = ["SarvamAdapter"]
