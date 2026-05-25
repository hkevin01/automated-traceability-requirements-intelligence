"""
ID: ATRI-AUTH-001
Purpose: Authentication and authorisation middleware for the ATRI API.
Requirement: Protect API endpoints with Bearer token authentication and RBAC.
Rationale: Regulated industries require documented access control for traceability systems.
           JWT-based auth provides stateless verification with role claims.
Inputs: HTTP Authorization header with Bearer token.
Outputs: Authenticated user principal (username + roles).
Preconditions: ATRI_AUTH_ENABLED must be true and ATRI_AUTH_BEARER_TOKEN must be set.
Postconditions: Unauthenticated requests receive HTTP 401; unauthorised receive 403.
Failure modes: Expired/invalid token raises HTTP 401; missing role raises HTTP 403.
Assumptions: Single-node deployment; token validation is shared-secret HMAC-SHA256.
Constraints: When auth_enabled=False the system uses the default system user - for dev only.
Verification: Unit tests cover token validation, role checking, and bypass mode.
References: OWASP API Security Top 10 - API1 Broken Object Level Authorization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from atri.config import settings

_bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Principal model
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class UserPrincipal:
    """
    ID: ATRI-AUTH-002
    Purpose: Represents an authenticated user session with roles.
    Inputs: username, roles list.
    Postconditions: has_role() is always safe to call.
    """
    username: str
    roles: list[str] = field(default_factory=list)

    def has_role(self, role: str) -> bool:
        """Return True if the user holds the specified role."""
        return role in self.roles

    def require_role(self, role: str) -> None:
        """
        Purpose: Raise HTTP 403 if the user does not hold `role`.
        Failure modes: Raises HTTPException(403) when role is absent.
        """
        if not self.has_role(role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' required.",
            )


# ---------------------------------------------------------------------------
# Token utilities
# ---------------------------------------------------------------------------

def create_access_token(username: str, roles: list[str]) -> str:
    """
    ID: ATRI-AUTH-003
    Purpose: Create a signed JWT access token for the given user.
    Inputs: username - subject claim; roles - list of role strings.
    Outputs: Signed JWT string.
    Side Effects: None.
    Failure modes: Returns empty string if jose is not available (dev fallback).
    """
    try:
        from jose import jwt  # noqa: PLC0415
    except ImportError:
        return settings.auth_bearer_token

    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expiry_minutes)
    payload = {
        "sub": username,
        "roles": roles,
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def _decode_jwt(token: str) -> dict[str, Any] | None:
    """
    ID: ATRI-AUTH-004
    Purpose: Decode and validate a JWT; return payload or None on failure.
    Inputs: token - raw JWT string.
    Outputs: decoded payload dict or None.
    Failure modes: Returns None on expiry, invalid signature, or import error.
    """
    try:
        from jose import JWTError, jwt  # noqa: PLC0415
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except Exception:
        return None


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
) -> UserPrincipal:
    """
    ID: ATRI-AUTH-005
    Purpose: FastAPI dependency that resolves the current authenticated user.
    Inputs: HTTP Authorization header (Bearer <token>).
    Outputs: UserPrincipal with username and roles.
    Preconditions: None (auth bypass when auth_enabled=False).
    Postconditions: Either returns a valid principal or raises HTTP 401.
    Failure modes:
      - auth_enabled=False: returns default system principal (dev mode).
      - Token is a static shared secret (settings.auth_bearer_token): parses roles from settings.
      - Valid JWT: decodes and returns claims.
      - Otherwise: raises HTTP 401.
    """
    if not settings.auth_enabled:
        default_roles = [r.strip() for r in settings.auth_default_roles.split(",") if r.strip()]
        return UserPrincipal(username=settings.auth_default_user, roles=default_roles)

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Shared-secret static token (simple use case)
    if token == settings.auth_bearer_token:
        default_roles = [r.strip() for r in settings.auth_default_roles.split(",") if r.strip()]
        return UserPrincipal(username=settings.auth_default_user, roles=default_roles)

    # JWT validation
    payload = _decode_jwt(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = payload.get("sub", "unknown")
    roles = payload.get("roles", [])
    if isinstance(roles, str):
        roles = [r.strip() for r in roles.split(",") if r.strip()]

    return UserPrincipal(username=username, roles=roles)


# ---------------------------------------------------------------------------
# Role-specific convenience dependencies
# ---------------------------------------------------------------------------

def require_analyst(user: UserPrincipal = Depends(get_current_user)) -> UserPrincipal:
    """
    ID: ATRI-AUTH-006
    Purpose: Dependency that enforces the 'analyst' or 'admin' role.
    Failure modes: Raises HTTP 403 if neither role is held.
    """
    if not (user.has_role("analyst") or user.has_role("admin")):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Analyst role required.")
    return user


def require_admin(user: UserPrincipal = Depends(get_current_user)) -> UserPrincipal:
    """
    ID: ATRI-AUTH-007
    Purpose: Dependency that enforces the 'admin' role.
    Failure modes: Raises HTTP 403 if admin role is absent.
    """
    user.require_role("admin")
    return user
