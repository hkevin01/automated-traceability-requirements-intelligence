"""
ID: ATRI-OIDC-001
Purpose: OIDC / SSO integration - validate JWT tokens issued by an external
         Identity Provider (IdP) using JWKS-based public key verification.
Requirement: When ATRI_OIDC_ENABLED=true, accept Bearer tokens signed by the
             configured OIDC issuer and map standard claims to ATRI roles.
Rationale: Enterprise deployments use Okta, Azure AD, Keycloak, or Auth0.
           Supporting OIDC lets those organisations authenticate without
           managing a separate ATRI-specific shared secret.
Inputs:
  Bearer token in Authorization header.
  JWKS endpoint discovered from ATRI_OIDC_JWKS_URI or
    {ATRI_OIDC_ISSUER}/.well-known/jwks.json.
Outputs: UserPrincipal populated from OIDC standard claims (sub, email, roles/
         groups claim).
Preconditions:
  ATRI_OIDC_ENABLED=true; ATRI_OIDC_ISSUER and ATRI_OIDC_CLIENT_ID set.
Postconditions: Token signature and expiry validated; claims mapped to ATRI roles.
Assumptions: JWKS keys are cached for 5 minutes (TTL configurable).
Side Effects: Outbound HTTPS request to JWKS endpoint on first call or after TTL.
Failure modes:
  - JWKS fetch fails: raises HTTP 503 with retry-after hint.
  - Token signature invalid: raises HTTP 401.
  - Token expired: raises HTTP 401.
  - Missing required claims: raises HTTP 403.
Constraints: Requires the cryptography extra of python-jose.
Verification: Unit tests use a locally generated RS256 key pair.
References: OpenID Connect Core 1.0; RFC 7517 (JWK); RFC 7519 (JWT).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JWKS cache - avoids a network round-trip on every request
# ---------------------------------------------------------------------------

_CACHE_TTL_SECONDS = 300  # 5 minutes

_jwks_cache: dict[str, Any] = {}
_jwks_cache_fetched_at: float = 0.0


def _fetch_jwks(jwks_uri: str) -> dict[str, Any]:
    """
    ID: ATRI-OIDC-002
    Purpose: Fetch and cache JWKS from the IdP; refresh after TTL expires.
    Inputs: jwks_uri - URL of the JWK Set document.
    Outputs: Parsed JWKS dict.
    Failure modes: Raises HTTP 503 if the fetch fails.
    Side Effects: Writes global _jwks_cache and _jwks_cache_fetched_at.
    """
    global _jwks_cache, _jwks_cache_fetched_at  # noqa: PLW0603

    now = time.monotonic()
    if _jwks_cache and (now - _jwks_cache_fetched_at) < _CACHE_TTL_SECONDS:
        return _jwks_cache

    try:
        import urllib.request  # noqa: PLC0415

        with urllib.request.urlopen(jwks_uri, timeout=5) as resp:  # noqa: S310
            import json  # noqa: PLC0415
            _jwks_cache = json.loads(resp.read())
            _jwks_cache_fetched_at = now
            return _jwks_cache
    except Exception as exc:
        logger.error("JWKS fetch failed from %s: %s", jwks_uri, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Identity provider JWKS endpoint is unavailable. Retry shortly.",
            headers={"Retry-After": "30"},
        ) from exc


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------

def validate_oidc_token(token: str) -> dict[str, Any]:
    """
    ID: ATRI-OIDC-003
    Purpose: Validate an OIDC JWT token against the IdP JWKS and return claims.
    Inputs: token - raw JWT string from the Authorization header.
    Outputs: Decoded claims dict.
    Preconditions: ATRI_OIDC_ENABLED=true; ATRI_OIDC_JWKS_URI or ATRI_OIDC_ISSUER set.
    Failure modes:
      - Signature invalid: raises HTTP 401.
      - Token expired: raises HTTP 401.
      - Audience mismatch: raises HTTP 401.
    """
    from atri.config import settings  # noqa: PLC0415

    jwks_uri = settings.oidc_jwks_uri or f"{settings.oidc_issuer.rstrip('/')}/.well-known/jwks.json"
    jwks = _fetch_jwks(jwks_uri)

    try:
        from jose import jwt as _jwt  # noqa: PLC0415
        from jose.exceptions import JWTError  # noqa: PLC0415
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="python-jose[cryptography] is required for OIDC validation.",
        ) from exc

    options: dict[str, Any] = {"verify_aud": bool(settings.oidc_audience)}
    kwargs: dict[str, Any] = {
        "algorithms": ["RS256", "RS384", "RS512", "ES256", "HS256"],
        "options": options,
    }
    if settings.oidc_audience:
        kwargs["audience"] = settings.oidc_audience
    if settings.oidc_issuer:
        kwargs["issuer"] = settings.oidc_issuer

    try:
        claims = _jwt.decode(token, jwks, **kwargs)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"OIDC token validation failed: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return claims


# ---------------------------------------------------------------------------
# Claims -> ATRI roles mapping
# ---------------------------------------------------------------------------

_CLAIM_NAMES = ("roles", "groups", "cognito:groups", "realm_access")

def extract_roles_from_claims(claims: dict[str, Any]) -> list[str]:
    """
    ID: ATRI-OIDC-004
    Purpose: Extract ATRI role strings from OIDC claims using common claim names.
    Inputs: claims - decoded JWT payload dict.
    Outputs: list of role strings (may be empty - caller handles access denial).
    Rationale: Different IdPs use different claim names for roles/groups.
               This function tries each known name in priority order.
    """
    for key in _CLAIM_NAMES:
        raw = claims.get(key)
        if isinstance(raw, list):
            return [str(r).lower() for r in raw]
        if isinstance(raw, dict):
            # Keycloak realm_access format: {"roles": [...]}
            inner = raw.get("roles", [])
            if isinstance(inner, list):
                return [str(r).lower() for r in inner]
        if isinstance(raw, str):
            return [r.strip().lower() for r in raw.split(",") if r.strip()]

    # Fall back to a default non-privileged role so the user is authenticated
    # but cannot perform privileged operations without explicit role assignment.
    return ["viewer"]
