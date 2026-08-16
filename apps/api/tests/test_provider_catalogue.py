"""The provider catalogue, and the field validation the connect form relies on.

Pure - no database and no network. What is under test is the contract three
other things depend on: the settings page renders whatever `fields` says, the
worker builds whatever `runtime_extra` promises, and `connect_provider` stores
exactly the keys a provider declared.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.v1.routes.integrations import _spec_to_out, _validated_fields
from app.core.crypto import pack_fields, unpack_fields
from app.domain.providers import (
    CALL_ROLES,
    PROVIDERS,
    ConnectMethod,
    ProviderRole,
    field_keys,
    for_role,
    spec,
)


class Row(dict):
    """An asyncpg record is subscriptable and raises KeyError; a dict is close
    enough for `unpack_fields`, which is written against exactly that."""


# --- the catalogue itself -----------------------------------------------------


def test_every_provider_has_at_least_one_field() -> None:
    """A provider with no fields renders a connect form with nothing in it."""
    for provider in PROVIDERS:
        assert provider.fields, provider.id


def test_every_provider_has_at_least_one_secret_field() -> None:
    """A credential made only of non-secret values is not a credential. Vonage's
    API key is public, its secret is not - so at least one field must be masked
    or nothing is actually being protected."""
    for provider in PROVIDERS:
        assert any(f.secret for f in provider.fields), provider.id


def test_field_keys_are_unique_within_a_provider() -> None:
    """Two fields sharing a key silently overwrite one another in the stored
    JSON, and the second one is the only value that survives."""
    for provider in PROVIDERS:
        keys = [f.key for f in provider.fields]
        assert len(keys) == len(set(keys)), provider.id


def test_every_provider_declares_at_least_one_role() -> None:
    for provider in PROVIDERS:
        assert provider.roles, provider.id


def test_only_openrouter_claims_a_login_flow() -> None:
    """`ConnectMethod.OAUTH` is a claim that a button opens a vendor's own login
    and gets a key back. Twilio Connect, Slack and HubSpot all have OAuth on
    paper, but each needs an app registered first - claiming one before that
    exists is a success state for something that never happens."""
    oauth = {p.id for p in PROVIDERS if p.connect is ConnectMethod.OAUTH}

    assert oauth == {"openrouter"}


def test_a_provider_that_drives_nothing_is_never_in_a_call_role() -> None:
    """Storage and automation vendors are stored-only. If one appeared under a
    call role it would be selectable on an agent and fail at dial time."""
    for provider in PROVIDERS:
        if provider.is_wired:
            continue
        assert not (provider.roles & CALL_ROLES), provider.id


def test_every_call_role_has_something_connectable_in_it() -> None:
    """An empty role renders a heading with no cards under it."""
    for role in CALL_ROLES:
        assert any(p.is_wired for p in for_role(role)), role


def test_a_provider_proxying_many_models_says_so() -> None:
    """`needs_model` drives a required model field on the agent. OpenRouter
    without it is a key that cannot say which of hundreds of models to run."""
    assert spec("openrouter") is not None
    assert spec("openrouter").needs_model is True
    assert spec("deepgram").needs_model is False


# --- what the settings page receives ------------------------------------------


def test_the_wire_format_sorts_roles_so_grouping_is_stable() -> None:
    """`roles` is a set on the server. Serialising it in iteration order makes a
    card jump between sections on refresh, which reads as a bug."""
    out = _spec_to_out(spec("deepgram"))

    assert out.roles == sorted(out.roles)
    assert set(out.roles) == {"transcriber", "voice"}


def test_the_wire_format_carries_whether_anything_reads_the_credential() -> None:
    assert _spec_to_out(spec("twilio")).wired is True
    assert _spec_to_out(spec("zapier")).wired is False


def test_no_secret_value_could_ever_ride_along_in_the_catalogue() -> None:
    """The catalogue is a public-ish description of vendors. It carries labels
    and placeholders, never a value."""
    out = _spec_to_out(spec("azure_openai"))

    assert all(not hasattr(f, "value") for f in out.fields)
    assert {f.key for f in out.fields} == {"api_key", "endpoint", "deployment"}


# --- validation ---------------------------------------------------------------


def test_the_declared_fields_are_accepted_and_trimmed() -> None:
    cleaned = _validated_fields(
        spec("twilio"), {"account_sid": "  AC1  ", "auth_token": "tok\n"}
    )

    assert cleaned == {"account_sid": "AC1", "auth_token": "tok"}


def test_a_missing_required_field_names_itself() -> None:
    with pytest.raises(HTTPException) as caught:
        _validated_fields(spec("twilio"), {"account_sid": "AC1"})

    assert caught.value.status_code == 400
    assert "Auth token" in caught.value.detail


def test_a_field_the_provider_never_declared_is_refused_not_dropped() -> None:
    """Silently discarding it would let someone believe they had configured
    something they had not, and the only sign would be an authentication
    failure on a live call - long after the form said it saved."""
    with pytest.raises(HTTPException) as caught:
        _validated_fields(
            spec("deepgram"), {"api_key": "dg", "region": "ap-south-1"}
        )

    assert caught.value.status_code == 400
    assert "region" in caught.value.detail


def test_an_optional_field_may_be_left_out() -> None:
    """Telnyx creates a connection when none is named, so demanding the id would
    block the ordinary case."""
    cleaned = _validated_fields(spec("telnyx"), {"api_key": "KEY1"})

    assert cleaned == {"api_key": "KEY1"}


def test_a_whitespace_only_required_field_is_still_missing() -> None:
    with pytest.raises(HTTPException):
        _validated_fields(spec("deepgram"), {"api_key": "   "})


def test_field_keys_reports_what_a_provider_will_accept() -> None:
    assert field_keys("aws_s3") == {
        "access_key_id",
        "secret_access_key",
        "region",
        "bucket",
    }
    assert field_keys("not-a-provider") == frozenset()


# --- storage shape ------------------------------------------------------------


def test_credentials_round_trip_through_one_ciphertext(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fields = {"api_key": "k", "endpoint": "https://x", "deployment": "gpt-4o"}

    packed = pack_fields(fields)

    assert unpack_fields(Row(fields_encrypted=packed)) == fields


def test_the_packed_blob_leaks_neither_values_nor_field_names() -> None:
    """Encrypting each value separately would leave the *names* in plaintext,
    which is enough to tell anyone reading the table which vendor a row is for
    and how it authenticates."""
    packed = pack_fields({"secret_access_key": "AKIA-secret", "bucket": "recordings"})

    assert "AKIA-secret" not in packed
    assert "secret_access_key" not in packed
    assert "bucket" not in packed


def test_a_row_written_before_the_migration_still_reads() -> None:
    """The fallback that lets `c8e1f4a29b76` ship without a decrypt-in-migration.
    Delete it once no row has a null `fields_encrypted`."""
    from app.core.crypto import encrypt

    legacy = Row(
        fields_encrypted=None,
        identifier_encrypted=encrypt("AC1"),
        secret_encrypted=encrypt("tok"),
    )

    assert unpack_fields(legacy) == {"identifier": "AC1", "secret": "tok"}


def test_the_new_shape_wins_over_the_legacy_columns() -> None:
    """`upsert` nulls the old columns on write, but precedence is asserted here
    so a half-migrated row can never authenticate with a stale secret."""
    from app.core.crypto import encrypt

    row = Row(
        fields_encrypted=pack_fields({"api_key": "new"}),
        identifier_encrypted=encrypt("old-id"),
        secret_encrypted=encrypt("old-secret"),
    )

    assert unpack_fields(row) == {"api_key": "new"}


def test_a_provider_serving_two_roles_stores_one_credential() -> None:
    """One Deepgram key does speech in and speech out. Two rows would mean an
    operator entering the same key twice and disconnecting it in one place
    leaving it live in the other."""
    deepgram = spec("deepgram")

    assert ProviderRole.TRANSCRIBER in deepgram.roles
    assert ProviderRole.VOICE in deepgram.roles
    assert len(deepgram.fields) == 1


# --- the routes the typed client actually calls -------------------------------


def test_the_integrations_router_exposes_every_method_the_client_uses() -> None:
    """`apps/web/lib/api.ts` calls all five of these.

    A route can disappear from a hand-edited module without a single test
    failing - nothing else here imports it by name, and the frontend only finds
    out as a 405 at the moment a user clicks. That is exactly how DELETE went
    missing during the per-provider-fields rewrite: every other test still
    passed, and the first sign was "Couldn't disconnect" in the interface.
    """
    from app.api.v1.routes.integrations import router

    exposed = {
        (method, route.path)
        for route in router.routes
        for method in getattr(route, "methods", set())
    }

    assert ("GET", "/api/v1/integrations/catalogue") in exposed
    assert ("GET", "/api/v1/integrations/providers") in exposed
    assert ("PUT", "/api/v1/integrations/providers/{provider}") in exposed
    assert ("DELETE", "/api/v1/integrations/providers/{provider}") in exposed
    assert ("POST", "/api/v1/integrations/providers/{provider}/oauth/exchange") in exposed


def test_the_telephony_router_exposes_both_connect_number_methods() -> None:
    """Same reasoning: the connect-a-number screen polls the GET, and losing it
    would look like provisioning silently never finishing."""
    from app.api.v1.routes.telephony import router

    exposed = {
        (method, route.path)
        for route in router.routes
        for method in getattr(route, "methods", set())
    }
    path = "/api/v1/voice-agents/{voice_agent_id}/connect-number"

    assert ("POST", path) in exposed
    assert ("GET", path) in exposed
