"""
ID: ATRI-TEST-ING-001
Purpose: Unit tests for all five ingestion adapters and the base IngestionResult model.
Requirement: Verify normalisation, field mapping, error handling, and content hashing.
"""

from __future__ import annotations

import csv
import io
import json
import textwrap

import pytest

from atri.ingestion.base import IngestionResult
from atri.ingestion.doors import DOORSAdapter
from atri.ingestion.jama import JamaAdapter
from atri.ingestion.sysml import SysMLAdapter
from atri.ingestion.visure import VisureAdapter


# ---------------------------------------------------------------------------
# IngestionResult
# ---------------------------------------------------------------------------

class TestIngestionResult:
    def test_content_hash_is_deterministic(self):
        r1 = IngestionResult(artifact_id="A", source="s", artifact_type="requirement", title="T", body="B")
        r2 = IngestionResult(artifact_id="A", source="s", artifact_type="requirement", title="T", body="B")
        assert r1.content_hash == r2.content_hash

    def test_content_hash_changes_on_body_change(self):
        r1 = IngestionResult(artifact_id="A", source="s", artifact_type="requirement", title="T", body="B1")
        r2 = IngestionResult(artifact_id="A", source="s", artifact_type="requirement", title="T", body="B2")
        assert r1.content_hash != r2.content_hash

    def test_empty_artifact_id_raises(self):
        with pytest.raises(ValueError, match="artifact_id"):
            IngestionResult(artifact_id="", source="s", artifact_type="requirement", title="T", body="B")

    def test_empty_source_raises(self):
        with pytest.raises(ValueError, match="source"):
            IngestionResult(artifact_id="A", source="", artifact_type="requirement", title="T", body="B")

    def test_to_dict_is_serialisable(self):
        r = IngestionResult(artifact_id="A", source="s", artifact_type="requirement", title="T", body="B")
        d = r.to_dict()
        assert json.dumps(d)  # no TypeError
        assert d["artifact_id"] == "A"
        assert d["content_hash"]

    def test_persist_appends_to_jsonl(self, tmp_path):
        from atri.ingestion.base import BaseIngestionAdapter
        items = [
            IngestionResult(artifact_id="A1", source="s", artifact_type="requirement", title="T1", body="B1"),
            IngestionResult(artifact_id="A2", source="s", artifact_type="requirement", title="T2", body="B2"),
        ]
        store = tmp_path / "store.jsonl"
        BaseIngestionAdapter.persist(items, store)
        lines = [line for line in store.read_text().splitlines() if line.strip()]
        assert len(lines) == 2
        first = json.loads(lines[0])
        assert first["artifact_id"] == "A1"

    def test_persist_is_append_only(self, tmp_path):
        from atri.ingestion.base import BaseIngestionAdapter
        store = tmp_path / "store.jsonl"
        items1 = [IngestionResult(artifact_id="X", source="s", artifact_type="requirement", title="T", body="B")]
        items2 = [IngestionResult(artifact_id="Y", source="s", artifact_type="requirement", title="T", body="B")]
        BaseIngestionAdapter.persist(items1, store)
        BaseIngestionAdapter.persist(items2, store)
        lines = [l for l in store.read_text().splitlines() if l.strip()]
        assert len(lines) == 2


# ---------------------------------------------------------------------------
# DOORS adapter
# ---------------------------------------------------------------------------

class TestDOORSAdapter:
    def test_csv_minimal(self):
        adapter = DOORSAdapter()
        content = "id,title,body\nREQ-1,Login,Users must authenticate.\nREQ-2,Logout,Users can log out."
        results = adapter.ingest(content.encode())
        assert len(results) == 2
        assert results[0].artifact_id == "REQ-1"
        assert results[0].title == "Login"

    def test_csv_normalises_type_requirement(self):
        adapter = DOORSAdapter()
        content = "id,title,body,type\nREQ-1,T,B,Functional Requirement"
        results = adapter.ingest(content.encode())
        assert results[0].artifact_type == "requirement"

    def test_csv_uses_row_number_when_id_missing(self):
        adapter = DOORSAdapter()
        content = "title,body\nTitle A,Body A"
        results = adapter.ingest(content.encode())
        assert results[0].artifact_id.startswith("DOORS-")

    def test_xml_reqif(self):
        adapter = DOORSAdapter()
        xmi = textwrap.dedent("""<?xml version='1.0'?>
        <REQ-IF>
          <CORE-CONTENT>
            <SPEC-OBJECTS>
              <SPEC-OBJECT IDENTIFIER="REQ-XMI-1">
                <LONG-NAME>Authentication Requirement</LONG-NAME>
              </SPEC-OBJECT>
            </SPEC-OBJECTS>
          </CORE-CONTENT>
        </REQ-IF>""")
        tmp = __import__("tempfile").NamedTemporaryFile(suffix=".xml", mode="w", delete=False)
        tmp.write(xmi)
        tmp.close()
        import os
        try:
            results = adapter.ingest(tmp.name)
            assert any("REQ-XMI-1" in r.artifact_id for r in results)
        finally:
            os.unlink(tmp.name)

    def test_empty_csv_returns_empty(self):
        adapter = DOORSAdapter()
        assert adapter.ingest(b"") == []

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            DOORSAdapter().ingest("/nonexistent/path/req.csv")


# ---------------------------------------------------------------------------
# Jama adapter
# ---------------------------------------------------------------------------

class TestJamaAdapter:
    def test_api_payload_dict(self):
        adapter = JamaAdapter()
        payload = {
            "data": [
                {
                    "id": 101,
                    "documentKey": "REQ-J1",
                    "itemType": "feature",
                    "fields": {"name": "Login feature", "description": "SSO integration"},
                    "version": "1",
                }
            ]
        }
        results = adapter.ingest(payload)
        assert len(results) == 1
        assert results[0].artifact_id == "JAMA-REQ-J1"
        assert results[0].title == "Login feature"
        assert results[0].artifact_type == "requirement"

    def test_api_payload_list(self):
        adapter = JamaAdapter()
        results = adapter.ingest([{"id": 1, "fields": {"name": "A", "description": "B"}}])
        assert len(results) == 1

    def test_api_payload_test_case_type(self):
        adapter = JamaAdapter()
        results = adapter.ingest([{"id": 2, "itemType": "test case", "fields": {"name": "T", "description": "D"}}])
        assert results[0].artifact_type == "test"

    def test_csv_ingestion(self):
        adapter = JamaAdapter()
        content = "id,name,description,item type\nREQ-1,Login,Auth requirement,functional requirement"
        results = adapter.ingest(content.encode())
        assert len(results) == 1
        assert results[0].title == "Login"

    def test_json_bytes_payload(self):
        adapter = JamaAdapter()
        payload = {"data": [{"id": 5, "documentKey": "REQ-5", "itemType": "design", "fields": {"name": "N", "description": "D"}}]}
        results = adapter.ingest(json.dumps(payload).encode())
        assert results[0].artifact_type == "design"


# ---------------------------------------------------------------------------
# Visure adapter
# ---------------------------------------------------------------------------

class TestVisureAdapter:
    def test_csv_basic(self):
        adapter = VisureAdapter()
        content = "id,title,description\nV-1,Auth Req,Authenticate before access.\nV-2,Log Req,Log all actions."
        results = adapter.ingest(content.encode())
        assert len(results) == 2
        assert results[0].artifact_id == "V-1"

    def test_csv_test_type(self):
        adapter = VisureAdapter()
        content = "id,title,description,type\nTC-1,TC,Test case,test case"
        results = adapter.ingest(content.encode())
        assert results[0].artifact_type == "test"

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            VisureAdapter().ingest("/no/such/file.csv")


# ---------------------------------------------------------------------------
# SysML adapter
# ---------------------------------------------------------------------------

class TestSysMLAdapter:
    def test_json_sysml_v2(self):
        adapter = SysMLAdapter()
        payload = [
            {"@id": "id1", "@type": "RequirementDefinition", "name": "AuthReq",
             "documentation": "System shall authenticate users."}
        ]
        results = adapter.ingest(json.dumps(payload).encode())
        assert len(results) == 1
        assert results[0].artifact_type == "requirement"
        assert "AuthReq" in results[0].title

    def test_json_block_type(self):
        adapter = SysMLAdapter()
        payload = [{"@id": "b1", "@type": "BlockDefinition", "name": "AuthModule", "documentation": "Auth block."}]
        results = adapter.ingest(json.dumps(payload).encode())
        assert results[0].artifact_type == "design"

    def test_json_unknown_type_skipped(self):
        adapter = SysMLAdapter()
        payload = [{"@id": "x1", "@type": "Diagram", "name": "Seq", "documentation": "Not traced."}]
        results = adapter.ingest(json.dumps(payload).encode())
        assert results == []

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            SysMLAdapter().ingest("/no/such/file.xmi")
