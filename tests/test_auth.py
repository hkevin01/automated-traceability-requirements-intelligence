"""
ID: ATRI-TEST-AUTH-001
Purpose: Unit tests for JWT authentication middleware, token creation/validation, and RBAC.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from atri.api.auth import (
    UserPrincipal,
    create_access_token,
    get_current_user,
    require_analyst,
    require_admin,
)
from atri.config import settings


@pytest.fixture(autouse=True)
def enable_auth(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "secret_key", "test-secret-key-for-unit-tests")
    yield


# ---------------------------------------------------------------------------
# Token creation / validation
# ---------------------------------------------------------------------------

class TestTokenCreation:
    def test_creates_token_string(self):
        token = create_access_token(username="alice", roles=["analyst"])
        assert isinstance(token, str)
        assert len(token) > 20

    def test_different_subjects_produce_different_tokens(self):
        t1 = create_access_token(username="alice", roles=["analyst"])
        t2 = create_access_token(username="bob", roles=["analyst"])
        assert t1 != t2

    def test_token_decodes_to_correct_subject(self):
        from jose import jwt as _jwt
        token = create_access_token(username="alice", roles=["admin"])
        data = _jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        assert data["sub"] == "alice"
        assert "admin" in data["roles"]


# ---------------------------------------------------------------------------
# get_current_user via FastAPI TestClient
# ---------------------------------------------------------------------------

def _make_test_app() -> FastAPI:
    app = FastAPI()

    @app.get("/whoami")
    def whoami(user: UserPrincipal = Depends(get_current_user)):
        return {"username": user.username, "roles": list(user.roles)}

    @app.get("/analyst-only")
    def analyst_only(_: UserPrincipal = Depends(require_analyst)):
        return {"ok": True}

    @app.get("/admin-only")
    def admin_only(_: UserPrincipal = Depends(require_admin)):
        return {"ok": True}

    return app


@pytest.fixture
def app_client():
    return TestClient(_make_test_app())


class TestGetCurrentUser:
    def test_valid_jwt_grants_access(self, app_client):
        token = create_access_token(username="alice", roles=["analyst"])
        resp = app_client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["username"] == "alice"

    def test_missing_header_returns_401(self, app_client):
        resp = app_client.get("/whoami")
        assert resp.status_code == 401

    def test_static_secret_accepted(self, app_client, monkeypatch):
        monkeypatch.setattr(settings, "auth_bearer_token", "my-static-secret")
        resp = app_client.get("/whoami", headers={"Authorization": "Bearer my-static-secret"})
        assert resp.status_code == 200

    def test_invalid_token_returns_401(self, app_client):
        resp = app_client.get("/whoami", headers={"Authorization": "Bearer garbage.token.here"})
        assert resp.status_code == 401


class TestRBAC:
    def test_analyst_can_access_analyst_route(self, app_client):
        token = create_access_token(username="alice", roles=["analyst"])
        resp = app_client.get("/analyst-only", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_viewer_cannot_access_analyst_route(self, app_client):
        token = create_access_token(username="viewer", roles=["viewer"])
        resp = app_client.get("/analyst-only", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_admin_can_access_admin_route(self, app_client):
        token = create_access_token(username="admin", roles=["admin"])
        resp = app_client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_analyst_cannot_access_admin_route(self, app_client):
        token = create_access_token(username="alice", roles=["analyst"])
        resp = app_client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403


class TestAuthDisabled:
    def test_no_header_returns_default_user_when_disabled(self, monkeypatch):
        monkeypatch.setattr(settings, "auth_enabled", False)
        app = _make_test_app()
        client = TestClient(app)
        resp = client.get("/whoami")
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "system"
