"""
ID: TEST-TENANT-001
Purpose: Unit tests for multi-tenant store path resolver.
"""
from __future__ import annotations
import pytest
from fastapi import HTTPException
from atri.core.tenancy import resolve_tenant, TenantContext
from atri.config import settings


def test_single_tenant_mode_returns_global_paths():
    # multi_tenant_enabled defaults to False
    ctx = resolve_tenant(x_tenant_id=None)
    assert isinstance(ctx, TenantContext)
    assert ctx.tenant_id == settings.default_tenant_id


def test_single_tenant_mode_ignores_header():
    ctx = resolve_tenant(x_tenant_id="some-org")
    # In single-tenant mode, the header is ignored
    assert ctx.tenant_id == settings.default_tenant_id


def test_multi_tenant_creates_scoped_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "multi_tenant_enabled", True)
    monkeypatch.setattr(settings, "tenant_data_root", str(tmp_path))
    ctx = resolve_tenant(x_tenant_id="acme-corp")
    assert ctx.tenant_id == "acme-corp"
    assert "acme-corp" in str(ctx.review_store_path)
    assert ctx.review_store_path.parent.exists()


def test_multi_tenant_path_isolation(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "multi_tenant_enabled", True)
    monkeypatch.setattr(settings, "tenant_data_root", str(tmp_path))
    ctx_a = resolve_tenant(x_tenant_id="tenant-a")
    ctx_b = resolve_tenant(x_tenant_id="tenant-b")
    assert ctx_a.review_store_path != ctx_b.review_store_path
    assert "tenant-a" in str(ctx_a.audit_store_path)
    assert "tenant-b" in str(ctx_b.audit_store_path)


def test_invalid_tenant_id_raises_400(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "multi_tenant_enabled", True)
    monkeypatch.setattr(settings, "tenant_data_root", str(tmp_path))
    with pytest.raises(HTTPException) as exc_info:
        resolve_tenant(x_tenant_id="../evil-traversal")
    assert exc_info.value.status_code == 400


def test_path_traversal_prevented(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "multi_tenant_enabled", True)
    monkeypatch.setattr(settings, "tenant_data_root", str(tmp_path))
    for bad_id in ("../../etc/passwd", "foo/bar", "foo bar", "a" * 65):
        with pytest.raises(HTTPException):
            resolve_tenant(x_tenant_id=bad_id)


def test_default_tenant_id_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "multi_tenant_enabled", True)
    monkeypatch.setattr(settings, "tenant_data_root", str(tmp_path))
    monkeypatch.setattr(settings, "default_tenant_id", "my-default")
    ctx = resolve_tenant(x_tenant_id=None)
    assert ctx.tenant_id == "my-default"
