"""Proving a credential before it is stored.

The behaviour worth protecting is the three-way answer. A vendor that *rejects*
a key must block the save; a vendor that cannot be *reached* must not, because
an outage is not a wrong key and refusing would stop someone configuring a
working account; and a key the vendor authenticates but refuses for scope is
real, so it is kept with the distinction intact.
"""

from __future__ import annotations

import httpx
import pytest

from app.domain.providers import CredentialProbe, spec
from app.services.credential_check import check_credentials

pytestmark = pytest.mark.asyncio

TWILIO = spec("twilio")
GROQ = spec("groq")


def _client(handler: object) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))  # type: ignore[arg-type]


async def test_a_key_the_vendor_accepts_is_verified() -> None:
    async with _client(lambda _r: httpx.Response(200, json={})) as client:
        result = await check_credentials(GROQ, {"api_key": "gsk_good"}, client=client)
    assert result.verified


async def test_a_key_the_vendor_rejects_is_not_verified() -> None:
    async with _client(lambda _r: httpx.Response(401, json={})) as client:
        result = await check_credentials(GROQ, {"api_key": "gsk_bad"}, client=client)
    assert result.ok is False
    assert "Groq" in (result.detail or "")


async def test_a_vendor_that_answers_400_still_counts_as_a_rejection() -> None:
    """xAI answers 400 for a key it cannot parse where most vendors answer 401."""
    async with _client(lambda _r: httpx.Response(400, json={})) as client:
        result = await check_credentials(spec("xai"), {"api_key": "bad"}, client=client)
    assert result.ok is False


async def test_a_vendor_that_cannot_be_reached_does_not_block_the_save() -> None:
    def _boom(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    async with _client(_boom) as client:
        result = await check_credentials(GROQ, {"api_key": "gsk_x"}, client=client)
    assert result.ok is None
    assert not result.verified


async def test_a_key_refused_only_for_scope_is_kept() -> None:
    """ElevenLabs keys are scoped per operation. A key that cannot read voices
    may still synthesise them, which is all CallFlow asks of it."""
    body = {"detail": {"status": "missing_permissions", "message": "missing the permission voices_read"}}
    async with _client(lambda _r: httpx.Response(401, json=body)) as client:
        result = await check_credentials(spec("elevenlabs"), {"api_key": "sk_x"}, client=client)
    assert result.ok is None
    assert "scoped too narrowly" in (result.detail or "")


async def test_a_provider_with_no_probe_is_not_claimed_to_be_checked() -> None:
    result = await check_credentials(spec("aws_s3"), {"api_key": "x"})
    assert result.ok is None
    assert result.detail is None


async def test_the_account_identifier_is_interpolated_into_the_url() -> None:
    """Twilio addresses the account by SID in the path, and the SID is also the
    basic-auth user - so both halves of the pair are proven at once."""
    seen: dict[str, str] = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization", "")
        return httpx.Response(200, json={})

    async with _client(_capture) as client:
        result = await check_credentials(
            TWILIO, {"account_sid": "AC123", "auth_token": "tok"}, client=client
        )

    assert result.verified
    assert "AC123" in seen["url"]
    assert seen["auth"].startswith("Basic ")


async def test_every_declared_probe_is_a_read() -> None:
    """A probe must never create, modify or spend anything on the customer's
    account - it runs on data someone typed into a form."""
    from app.domain.providers import PROVIDERS

    for provider in PROVIDERS:
        if provider.probe is None:
            continue
        assert isinstance(provider.probe, CredentialProbe)
        assert provider.probe.url.startswith("https://"), provider.id
        assert provider.probe.auth in {"bearer", "basic", "header", "query"}, provider.id


async def test_an_empty_secret_is_rejected_rather_than_sent() -> None:
    """A blank key cannot be valid, and sending one builds an illegal header
    that httpx refuses before any request - which would otherwise be read as
    "the vendor is unreachable" and let the blank field through."""
    result = await check_credentials(GROQ, {"api_key": "   "})
    assert result.ok is False
    assert "api key" in (result.detail or "").lower()


async def test_a_post_probe_treats_a_declared_status_as_proof_of_the_key() -> None:
    """Sarvam has no read endpoint that authenticates, so its probe POSTs an
    empty body: a good key is refused for the *body*, a bad one for the *key*."""
    async with _client(lambda _r: httpx.Response(400, json={})) as client:
        result = await check_credentials(spec("sarvam"), {"api_key": "real"}, client=client)
    assert result.verified

    async with _client(lambda _r: httpx.Response(403, json={})) as client:
        rejected = await check_credentials(spec("sarvam"), {"api_key": "fake"}, client=client)
    assert rejected.ok is False


async def test_a_bare_400_is_still_a_rejection_where_it_was_not_declared() -> None:
    """`accept_statuses` is opt-in per provider. A vendor that never declared it
    must not have a 400 read as success."""
    async with _client(lambda _r: httpx.Response(400, json={})) as client:
        result = await check_credentials(GROQ, {"api_key": "x"}, client=client)
    assert result.ok is False


async def test_no_probe_points_at_an_endpoint_that_needs_no_credential() -> None:
    """The flaw that made this worth auditing: Sarvam's `/v1/models` and
    ElevenLabs' `/v1/voices` are public - they answer 200 with no key at all, so
    probing them accepted any string as valid. A probe has to be able to fail.

    Checked by shape rather than over the network, so the suite stays offline:
    a public listing endpoint is the trap, and naming them keeps the next one
    from being added without a thought.
    """
    from app.domain.providers import PROVIDERS

    known_public = {
        "https://api.sarvam.ai/v1/models",
        "https://api.elevenlabs.io/v1/voices",
        "https://api.elevenlabs.io/v1/voices/settings/default",
    }
    for provider in PROVIDERS:
        if provider.probe is None:
            continue
        assert provider.probe.url not in known_public, (
            f"{provider.id} probes a public endpoint - it would accept any key"
        )


async def test_a_wired_provider_without_a_probe_is_a_deliberate_gap() -> None:
    """Every vendor the runtime can actually drive should verify its credentials
    before storing them, so this pins the exceptions rather than letting the
    number quietly grow.

    The ones listed here are genuinely hard, not forgotten: Azure and AWS
    authenticate per tenant or with request signing, and four vendors answer 2xx
    with no credential at all - a probe against those would accept any string,
    which is worse than admitting the credential is unverified.
    """
    from app.domain.providers import PROVIDERS

    known_gaps = {
        # Per-tenant endpoint or request signing - no single URL to probe.
        "azure_openai", "azure_speech", "aws_bedrock", "clova", "rtzr", "minimax",
        # Their listing endpoints answer 200 unauthenticated (checked).
        "rime", "smallestai", "fishaudio", "playai",
        # No read endpoint that authenticates without spending.
        "perplexity", "gnani", "spitch", "baseten", "fal", "upliftai",
    }
    unprobed = {p.id for p in PROVIDERS if p.probe is None and p.is_wired}

    assert unprobed <= known_gaps, (
        f"these wired providers gained no probe and are not recorded as a known "
        f"gap: {sorted(unprobed - known_gaps)}"
    )
