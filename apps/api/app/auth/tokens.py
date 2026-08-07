"""Access-token verification."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import jwt
from jwt import PyJWKClient

from app.core.config import config

# Supabase signs user tokens with aud="authenticated".
EXPECTED_AUDIENCE = "authenticated"
ASYMMETRIC_ALGORITHMS = ["ES256", "RS256"]
JWKS_CLIENT_TTL_SECONDS = 600
JWKS_FETCH_TIMEOUT_SECONDS = 5

# Tolerance for clock drift between this host and the auth server. Without it a
# token whose `iat` is a second ahead of our clock is rejected as immature, which
# is a real failure mode on any host that is not tightly NTP-synced — and it
# presents as "valid credentials rejected", which is miserable to diagnose.
# Applies to exp as well, so it is kept small.
CLOCK_SKEW_LEEWAY = timedelta(seconds=30)


class InvalidToken(Exception):
    """The token is absent, malformed, expired, or not ours."""


@dataclass(frozen=True)
class TokenClaims:
    auth_user_id: str
    email: str | None
    role: str
    expires_at: int
    raw: dict[str, Any]


class TokenVerifier:
    """Verifies Supabase access tokens.

    This project uses publishable/secret keys, which means asymmetric signing: tokens
    verify against the project's public JWKS and the API holds no shared secret.
    Legacy HS256 projects fall back to SUPABASE_JWT_SECRET.

    Audience and issuer are checked, not just the signature — a validly-signed token
    from a different Supabase project must still be rejected.
    """

    def __init__(self) -> None:
        self._jwks_client: PyJWKClient | None = None
        self._jwks_client_age: float = 0.0

    def verify(self, token: str) -> TokenClaims:
        if not token.strip():
            raise InvalidToken("No access token supplied.")

        try:
            payload = self._decode(token)
        except jwt.ExpiredSignatureError as exc:
            raise InvalidToken("The access token has expired.") from exc
        except jwt.InvalidAudienceError as exc:
            raise InvalidToken("The access token was issued for a different audience.") from exc
        except jwt.InvalidIssuerError as exc:
            raise InvalidToken("The access token was issued by a different project.") from exc
        except jwt.PyJWTError as exc:
            # Bad signature, malformed structure, unknown key id, and the rest.
            raise InvalidToken(f"The access token is not valid: {type(exc).__name__}") from exc

        subject = payload.get("sub")
        if not subject:
            raise InvalidToken("The access token carries no subject.")

        return TokenClaims(
            auth_user_id=str(subject),
            email=payload.get("email"),
            role=str(payload.get("role", EXPECTED_AUDIENCE)),
            expires_at=int(payload["exp"]),
            raw=payload,
        )

    def _decode(self, token: str) -> dict[str, Any]:
        options = {
            "require": ["exp", "sub"],
            "verify_exp": True,
            "verify_aud": True,
            "verify_iss": bool(self._issuer),
        }

        if config.supabase_jwks_url:
            key = self._signing_key(token)
            algorithms = ASYMMETRIC_ALGORITHMS
        elif config.supabase_jwt_secret:
            key = config.supabase_jwt_secret
            algorithms = ["HS256"]
        else:
            raise InvalidToken(
                "No token verification method is configured. Set SUPABASE_JWKS_URL "
                "(preferred) or SUPABASE_JWT_SECRET."
            )

        return jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience=EXPECTED_AUDIENCE,
            issuer=self._issuer,
            leeway=CLOCK_SKEW_LEEWAY,
            options=options,
        )

    def _signing_key(self, token: str):
        return self._client().get_signing_key_from_jwt(token).key

    def _client(self) -> PyJWKClient:
        now = time.monotonic()
        if self._jwks_client is None or now - self._jwks_client_age > JWKS_CLIENT_TTL_SECONDS:
            self._jwks_client = PyJWKClient(
                config.supabase_jwks_url,
                cache_keys=True,
                # A hung JWKS fetch would stall every request queued behind it.
                timeout=JWKS_FETCH_TIMEOUT_SECONDS,
            )
            self._jwks_client_age = now
        return self._jwks_client

    @property
    def _issuer(self) -> str | None:
        if not config.supabase_url:
            return None
        return f"{config.supabase_url}/auth/v1"


token_verifier = TokenVerifier()
