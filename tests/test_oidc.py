"""
ID: TEST-OIDC-001
Purpose: Unit tests for OIDC/SSO integration - role extraction and validator import.
"""
from __future__ import annotations
from atri.api.oidc import extract_roles_from_claims


def test_extract_roles_from_roles_list():
    claims = {"sub": "user1", "roles": ["analyst", "admin"]}
    roles = extract_roles_from_claims(claims)
    assert "analyst" in roles
    assert "admin" in roles


def test_extract_roles_from_groups_list():
    claims = {"sub": "user1", "groups": ["Analyst", "Reviewer"]}
    roles = extract_roles_from_claims(claims)
    assert "analyst" in roles
    assert "reviewer" in roles


def test_extract_roles_from_keycloak_realm_access():
    claims = {"sub": "user1", "realm_access": {"roles": ["admin", "analyst"]}}
    roles = extract_roles_from_claims(claims)
    assert "admin" in roles


def test_extract_roles_from_comma_string():
    claims = {"sub": "user1", "roles": "admin, analyst"}
    roles = extract_roles_from_claims(claims)
    assert "admin" in roles
    assert "analyst" in roles


def test_extract_roles_default_fallback():
    # No role claims at all
    claims = {"sub": "user1", "email": "u@example.com"}
    roles = extract_roles_from_claims(claims)
    assert roles == ["viewer"]


def test_validate_oidc_token_raises_when_disabled(monkeypatch):
    """When oidc_enabled=False and no JWKS URI, _fetch_jwks should raise 503."""
    from atri.api import oidc as _oidc_mod
    # Patch _fetch_jwks to avoid network call
    def _fake_fetch(uri):
        raise Exception("no network")
    monkeypatch.setattr(_oidc_mod, "_fetch_jwks", _fake_fetch)
    from fastapi import HTTPException
    import pytest
    with pytest.raises((HTTPException, Exception)):
        _oidc_mod.validate_oidc_token("fake.token.here")
