"""Proving a stored credential actually works.

`services/`, because it is I/O against a vendor driven by a rule the domain
declares. `domain/providers.py` says *what* to call and how to present the
secret; this module makes the call and turns the answer into something an
operator can act on.

The whole point is to fail at the form rather than on a live call. Before this,
`PUT /integrations/providers/{provider}` stored whatever was typed and the card
read "Connected" - a wrong key surfaced much later as a sync that returned
nothing or a call that connected to silence, a long way from the screen that
caused it (CLAUDE.md non-negotiable #9).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.domain.providers import CredentialProbe, ProviderSpec

log = logging.getLogger("app.services.credential_check")

#: Long enough for a slow vendor, short enough that a hung endpoint does not
#: hold the request open - a credential that cannot answer in this window is
#: not one a call should depend on either.
_TIMEOUT = 10.0


@dataclass(frozen=True)
class CheckResult:
    """What a probe found. `ok=None` means no probe is declared for this
    provider, which is different from a credential that failed."""

    ok: bool | None
    detail: str | None = None

    @property
    def verified(self) -> bool:
        return self.ok is True


def _request(probe: CredentialProbe, fields: dict[str, str]) -> tuple[str, dict[str, str], dict[str, str], tuple[str, str] | None]:
    """The URL, headers, params and basic-auth pair this probe needs."""
    secret = fields.get(probe.field, "")
    url = probe.url.format(field=fields.get(probe.basic_user_field or probe.field, ""))

    headers: dict[str, str] = {}
    params: dict[str, str] = {}
    auth: tuple[str, str] | None = None

    if probe.auth == "bearer":
        headers["Authorization"] = f"Bearer {secret}"
    elif probe.auth == "header" and probe.header:
        headers[probe.header] = secret
    elif probe.auth == "query" and probe.header:
        params[probe.header] = secret
    elif probe.auth == "basic":
        auth = (fields.get(probe.basic_user_field or "", ""), secret)

    return url, headers, params, auth


#: A vendor saying "this key is real but not allowed to do *that*". The key
#: authenticated - which is what a probe is for - so a scope the probe happens
#: to need is not grounds to refuse the credential. ElevenLabs keys are scoped
#: per operation, and a key that can synthesise speech need not hold
#: `voices_read`; rejecting it would block a key that works for the only thing
#: CallFlow asks of it.
_SCOPE_MARKERS = ("missing_permissions", "missing the permission", "insufficient_scope")


def _is_scope_refusal(body: str) -> bool:
    lowered = body.lower()
    return any(marker in lowered for marker in _SCOPE_MARKERS)


def _explain(provider: ProviderSpec, status_code: int) -> str:
    """The vendor's status turned into the thing to go and do.

    Deliberately not the response body: vendors echo request details back, and
    a credential can appear in one. The status is what distinguishes "wrong
    key" from "right key, wrong plan" - which need different fixes.
    """
    # 400 among them because vendors disagree: xAI answers 400 for a key it
    # cannot parse where most answer 401, and "your key is wrong" is the same
    # instruction either way.
    if status_code in (400, 401, 403):
        return (
            f"{provider.name} rejected these credentials. "
            f"Check them at {provider.docs_url} and paste them again."
        )
    if status_code == 404:
        return (
            f"{provider.name} accepted the request but found no such account. "
            "Check the account identifier."
        )
    if status_code == 429:
        return (
            f"{provider.name} is rate-limiting this key right now. "
            "It may be valid - try again in a minute."
        )
    return f"{provider.name} answered {status_code}. The credentials were not confirmed."


async def check_credentials(
    provider: ProviderSpec,
    fields: dict[str, str],
    *,
    client: httpx.AsyncClient | None = None,
) -> CheckResult:
    """Ask the vendor whether these credentials work.

    Never raises. A provider with no declared probe returns `ok=None`, and a
    vendor that cannot be reached returns `ok=None` with the reason - neither is
    the same as a credential the vendor actively rejected, and treating an
    outage as a bad key would stop someone configuring a working account.
    """
    probe = provider.probe
    if probe is None:
        return CheckResult(ok=None)

    # An empty secret cannot be a valid credential, and sending it would build
    # an illegal header that httpx refuses before any request - which would then
    # read as "the vendor is unreachable" and let a blank field through.
    if not fields.get(probe.field, "").strip():
        # "needs an API key", not "needs a API key" - the labels are nouns
        # written for a form, and this sentence is the only place they are
        # read as prose.
        field_label = next(
            (f.label for f in provider.fields if f.key == probe.field), probe.field
        )
        return CheckResult(ok=False, detail=(
                f"{provider.name} needs "
                f"{'an' if field_label[:1].lower() in 'aeiou' else 'a'} "
                f"{field_label.lower()}."
            ),)

    url, headers, params, auth = _request(probe, fields)
    http = client or httpx.AsyncClient(timeout=_TIMEOUT)
    try:
        # An empty body on the POST form: the point is to be refused, either for
        # the key or for the body, and to create nothing either way.
        response = await http.request(
            probe.method,
            url,
            headers=headers,
            params=params,
            auth=auth,
            json={} if probe.method == "POST" else None,
        )
    except httpx.HTTPError as exc:
        log.info("could not reach %s to verify a credential: %s", provider.id, type(exc).__name__)
        return CheckResult(
            ok=None,
            detail=(
                f"{provider.name} could not be reached to confirm these credentials. "
                "They were saved - try a sync to check them."
            ),
        )
    finally:
        if client is None:
            await http.aclose()

    if response.is_success:
        return CheckResult(ok=True)

    # "Your key is fine, your request is not" - which is exactly what a POST
    # probe with an empty body is asking for. Only statuses the provider itself
    # declares count, so a bare 400 from a vendor that never opted in still
    # reads as a rejection.
    if response.status_code in probe.accept_statuses:
        return CheckResult(ok=True)

    if _is_scope_refusal(response.text):
        # Authenticated, then refused for scope. The credential is real, so it
        # is stored - with the vendor's own distinction kept, because a key that
        # cannot read voices may still synthesise them and only the operator
        # knows which scopes they meant to grant.
        log.info("%s accepted the key but refused the probe's scope", provider.id)
        return CheckResult(
            ok=None,
            detail=(
                f"{provider.name} accepted this key but it is scoped too narrowly to "
                "confirm here. It was saved - if calls fail, widen the key's permissions."
            ),
        )

    return CheckResult(ok=False, detail=_explain(provider, response.status_code))


__all__ = ["CheckResult", "check_credentials"]
