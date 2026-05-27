# ATRI Roadmap

## Scope Expansion

The expanded ATRI scope focuses on traceability support for NASA IV&V-style workflows across requirements, design, code, tests, hazards, mitigations, and interfaces.

## Epics

### 1. Requirements Ingestion Layer

- Ingest DOORS and DOORS Next exports.
- Ingest Jama and Visure exports.
- Parse Word, PDF, and SysML sources into a normalized artifact schema.

Acceptance criteria:

- Imported artifacts retain stable IDs and source provenance.
- Failed parses return actionable validation errors.
- Ingestion produces a common schema for downstream analysis.

### 2. Semantic Analysis Engine

- Generate embeddings for artifact content.
- Rank candidate links by similarity and pattern-based heuristics.
- Surface confidence and rationale for analyst review.

Acceptance criteria:

- Link suggestions are explainable.
- Low-confidence outputs fall back to deterministic rules.
- Analysts can validate or reject suggested links.

### 3. Traceability Graph Store

- Persist artifacts as nodes and trace links as edges.
- Store risk, status, confidence, and provenance on graph edges.
- Support impact traversal across linked artifacts.

Acceptance criteria:

- Graph queries return affected upstream and downstream artifacts.
- Edge metadata is queryable for audits.
- Store adapters can swap between local and enterprise backends.

### 4. Analyst Review Interface

- Show proposed links with confidence and rationale.
- Support accept and reject actions.
- Preserve human-in-the-loop IV&V independence.

Acceptance criteria:

- Review actions are captured as audit events.
- Rejected links are excluded from authoritative trace views.
- Accepted links become available to impact analysis and dashboards.

### 5. Dashboards and Reporting

- Show coverage, orphaned artifacts, high-risk modules, and volatility.
- Provide exportable summaries for mission reviews.
- Track verification progress across releases.

Acceptance criteria:

- Dashboard metrics update from authoritative trace data.
- Reports are reproducible from stored evidence.
- Metrics support program and IV&V leadership views.

## Delivery Order

1. Ingestion and normalization.
2. Semantic link suggestion.
3. Graph persistence and impact queries.
4. Analyst review workflow.
5. Dashboards and reporting.

## Suggested First Milestones

- Add a file-based artifact ingestion adapter.
- Add vector retrieval for semantic search.
- Add graph persistence behind the existing services.
- Add review-state tracking for proposed links.
---

### 6. LLM Enrichment Engine - IMPLEMENTED

**Goal:** Generate human-readable rationale for every trace link using LLM intelligence, replacing opaque token-overlap scores with engineer-friendly explanations.

**Status:** Complete. Shipped in the current sprint.

**Acceptance criteria:**

- `POST /api/v1/traceability/link-explain` returns a rationale string for any source/target artifact pair.
- Fallback heuristic is returned when `ATRI_LLM_RATIONALE_ENABLED=false` (default) or when the provider API is unreachable.
- Results are cached to `data/processed/llm_rationale_cache.json` keyed by SHA-256 of artifact bodies; repeated calls do not cost tokens.
- Both OpenAI Chat Completions API and Azure OpenAI endpoints are supported via env vars.
- Unit tests cover: fallback path, cache hit, `to_dict()` contract, cache clear, dataclass defaults.

**Implementation:**

- `src/atri/core/services/llm_rationale.py` - `LLMRationaleService` + `RationaleResult`
- `src/atri/api/routes/traceability.py` - `POST /link-explain` endpoint
- New config fields: `ATRI_LLM_RATIONALE_ENABLED`, `ATRI_OPENAI_API_KEY`, `ATRI_OPENAI_MODEL`, `ATRI_AZURE_OPENAI_*`

---

### 7. Real-Time Streaming Dashboard - IMPLEMENTED

**Goal:** Push live audit events and KPI snapshots to dashboard clients without polling.

**Status:** Complete. Shipped in the current sprint.

**Acceptance criteria:**

- `WS /api/v1/stream/events` accepts WebSocket connections with optional `?topic=audit|dashboard|all`.
- Dashboard snapshot is pushed immediately on connect for `topic=dashboard` or `topic=all`.
- New audit events are pushed within the next poll interval (default 2 s).
- `GET /api/v1/stream/status` returns the count of connected clients.
- `broadcast_audit_event()` helper is importable by other services for push notifications.

**Implementation:**

- `src/atri/api/routes/stream.py` - WebSocket router with `_ConnectionManager` pub-sub and async poll loop
- `src/atri/main.py` - stream router registered
- Tests in `tests/test_stream.py`

---

### 8. SSO / OIDC Integration - IMPLEMENTED

**Goal:** Allow enterprise deployments to authenticate users through their existing Identity Provider (Okta, Azure AD, Keycloak, Auth0) without managing a separate ATRI secret.

**Status:** Complete. Shipped in the current sprint.

**Acceptance criteria:**

- When `ATRI_OIDC_ENABLED=true`, Bearer tokens signed by the configured IdP are accepted without needing `ATRI_AUTH_BEARER_TOKEN`.
- JWKS keys are fetched from `ATRI_OIDC_JWKS_URI` (or discovered from `{issuer}/.well-known/jwks.json`) and cached for 5 minutes.
- Roles/groups are extracted from `roles`, `groups`, `cognito:groups`, or `realm_access.roles` claims.
- OIDC validation is transparent to all existing ATRI role guards (`require_analyst`, `require_admin`).
- Unit tests cover: list roles claim, groups claim, Keycloak realm_access format, comma-delimited string, missing-claim fallback to `viewer`.

**Implementation:**

- `src/atri/api/oidc.py` - `validate_oidc_token()`, `extract_roles_from_claims()`, JWKS cache
- `src/atri/api/auth.py` - OIDC path added to `get_current_user()` before local JWT check
- New config fields: `ATRI_OIDC_ENABLED`, `ATRI_OIDC_ISSUER`, `ATRI_OIDC_CLIENT_ID`, `ATRI_OIDC_JWKS_URI`, `ATRI_OIDC_AUDIENCE`

---

### 9. Multi-Tenant Graph Isolation - IMPLEMENTED

**Goal:** Allow multiple independent programs (tenants) to share a single ATRI deployment with complete data isolation at the storage layer.

**Status:** Complete. Shipped in the current sprint.

**Acceptance criteria:**

- When `ATRI_MULTI_TENANT_ENABLED=true`, each tenant's data lives under `data/tenants/{tenant_id}/`.
- Tenant is resolved from the `X-Tenant-ID` request header; missing header falls back to `ATRI_DEFAULT_TENANT_ID`.
- `tenant_id` is validated against `[a-zA-Z0-9_-]{1,64}` to prevent path traversal attacks.
- All store paths (reviews, history, graph, audit, ingestion, vector index) are isolated per tenant.
- In single-tenant mode (`ATRI_MULTI_TENANT_ENABLED=false`, the default), behaviour is identical to pre-feature operation.
- Unit tests cover: single-tenant passthrough, path isolation between tenants, invalid ID rejection (400), path traversal prevention, default ID fallback.

**Implementation:**

- `src/atri/core/tenancy.py` - `TenantContext` frozen dataclass + `resolve_tenant()` FastAPI dependency
- New config fields: `ATRI_MULTI_TENANT_ENABLED`, `ATRI_DEFAULT_TENANT_ID`, `ATRI_TENANT_DATA_ROOT`
- Tests in `tests/test_tenant.py`

---

## Delivery Order (Updated)

| # | Epic | Status |
|---|------|--------|
| <sub>1</sub> | <sub>Requirements Ingestion Layer</sub> | <sub>✅ Complete</sub> |
| <sub>2</sub> | <sub>Intelligent Trace Linking</sub> | <sub>✅ Complete</sub> |
| <sub>3</sub> | <sub>Impact Analysis</sub> | <sub>✅ Complete</sub> |
| <sub>4</sub> | <sub>Gap Detection</sub> | <sub>✅ Complete</sub> |
| <sub>5</sub> | <sub>Audit Trail</sub> | <sub>✅ Complete</sub> |
| <sub>6</sub> | <sub>LLM Enrichment Engine</sub> | <sub>✅ Complete</sub> |
| <sub>7</sub> | <sub>Real-Time Streaming Dashboard</sub> | <sub>✅ Complete</sub> |
| <sub>8</sub> | <sub>SSO / OIDC Integration</sub> | <sub>✅ Complete</sub> |
| <sub>9</sub> | <sub>Multi-Tenant Graph Isolation</sub> | <sub>✅ Complete</sub> |
| <sub>10</sub> | <sub>Neo4j / Graph DB Production Backend</sub> | <sub>✅ Complete</sub> |
| <sub>11</sub> | <sub>CI/CD Pipeline & Deployment Automation</sub> | <sub>✅ Complete</sub> |
| <sub>12</sub> | <sub>Frontend Polish & UX Hardening</sub> | <sub>✅ Complete</sub> |
| <sub>13</sub> | <sub>Compliance Reporting</sub> | <sub>✅ Complete</sub> |
| <sub>14</sub> | <sub>Webhook Notifications</sub> | <sub>✅ Complete</sub> |
| <sub>15</sub> | <sub>Observability (Metrics + Structured Logging)</sub> | <sub>✅ Complete</sub> |

> **Note:** All 15 epics are fully implemented with 149 passing tests.

---

### 10. Neo4j Production Graph Backend - IMPLEMENTED

**Goal:** Allow production deployments to replace the in-process networkx JSON store with a Neo4j graph database without changing any route handler code.

**Status:** Complete. Shipped in the current sprint.

**Acceptance criteria:**

- When `ATRI_GRAPH_BACKEND_URI` is set, all graph operations (replace_graph, adjacency_map, stats, get_downstream) are routed to Neo4jGraphStore.
- When `ATRI_GRAPH_BACKEND_URI` is empty (default), the existing TraceGraphStore (JSON file) is used unchanged.
- Neo4jGraphStore singleton is cached per process; `reset_neo4j_singleton()` is available for tests.
- Neo4j connection failure is caught at startup; store returns no-op responses (available=False) so the API continues to serve requests.
- Unit tests cover: local fallback, Neo4j selection, singleton caching, reset, unavailable graceful handling.

**Implementation:**

- `src/atri/core/services/graph_factory.py` - `make_graph_store()` factory + singleton management
- `src/atri/api/routes/traceability.py`, `impact.py`, `dashboard.py` - switched from direct TraceGraphStore to `make_graph_store(tenant.graph_store_path)`
- New tests in `tests/test_graph_factory.py` (6 tests)

---

### 11. CI/CD Pipeline Automation - IMPLEMENTED

**Goal:** Automate linting, testing, Docker builds, and release image publishing on every push and version tag.

**Status:** Complete. Shipped in the current sprint.

**Acceptance criteria:**

- On every push and pull request: ruff lint runs first; then tests run against Python 3.11 and 3.12 in parallel; then a Docker image smoke-build runs on test success.
- Test coverage is uploaded to Codecov when the CODECOV_TOKEN secret is set.
- On version tags (`v*`): Docker image is built and pushed to GitHub Container Registry with semver, minor-version, and SHA tags.
- Dependabot keeps Python dependencies and GitHub Actions up to date with weekly PRs.

**Implementation:**

- `.github/workflows/ci.yml` - lint + matrix test + Docker smoke (enhanced from single-job)
- `.github/workflows/release.yml` - GHCR Docker publish with Buildx cache
- `.github/dependabot.yml` - pip and github-actions weekly updates

---

### 12. Frontend Polish and UX Hardening - IMPLEMENTED

**Goal:** Upgrade the React frontend from scaffold to a functional tool with live data, impact analysis, and real-time event feed.

**Status:** Complete. Shipped in the current sprint.

**Acceptance criteria:**

- Dashboard shows a live connection indicator (green dot); WebSocket dashboard topic auto-connects and updates KPI cards in real time without polling.
- Dashboard has a manual Refresh button for users who prefer pull semantics.
- Impact Analysis page submits artifact IDs to `POST /api/v1/impact/analyze` and renders upstream/downstream results table with distance badges.
- Live Feed page connects to `WS /api/v1/stream/events` with topic selector (all/audit/dashboard); auto-reconnects every 5 s on disconnect; shows event count and clear button.
- All pages show inline error messages when the API is unreachable.
- Navigation includes Impact and Live Feed pages.

**Implementation:**

- `frontend/src/App.jsx` - updated nav (5 pages: Dashboard, Traceability, Impact, Ingestion, Live Feed)
- `frontend/src/components/Dashboard.jsx` - WebSocket live KPI updates + Refresh button
- `frontend/src/components/ImpactAnalysis.jsx` - new page for impact traversal
- `frontend/src/components/LiveFeed.jsx` - new WebSocket event stream page

---

### 13. Compliance Reporting - IMPLEMENTED

**Goal:** Provide exportable audit + review evidence packages required for DO-178C / IEC-62304 program reviews.

**Status:** Complete.

**Acceptance criteria:**

- `GET /api/v1/reports/compliance` returns JSON summary of audit events, review decisions, actor breakdowns, and event-type counts.
- `GET /api/v1/reports/compliance/audit.csv` returns all audit events as a CSV attachment.
- `GET /api/v1/reports/compliance/reviews.csv` returns all review records as a CSV attachment.
- All endpoints are tenant-scoped via `Depends(resolve_tenant)`.
- Missing data files are handled gracefully (empty report, not an error).

**Implementation:**

- `src/atri/core/services/compliance_report.py` - `ComplianceReportService` reads audit JSONL + reviews JSON; `ComplianceReport` dataclass with CSV/JSON serialisers.
- `src/atri/api/routes/reports.py` - 3 GET endpoints registered under `/api/v1/reports`.
- `tests/test_compliance_report.py` - 9 unit + integration tests.

---

### 14. Webhook Notifications - IMPLEMENTED

**Goal:** Allow external systems to receive ATRI events via outbound HTTP POST without polling.

**Status:** Complete.

**Acceptance criteria:**

- `POST /api/v1/notifications/webhooks` registers a webhook with URL, optional HMAC-SHA256 secret, and optional event filter.
- `GET /api/v1/notifications/webhooks` lists all registered webhooks (secret redacted).
- `DELETE /api/v1/notifications/webhooks/{name}` removes a webhook by name; 404 if not found.
- `POST /api/v1/notifications/webhooks/test` sends a test ping to a named webhook; 404 if not found.
- Delivery includes `X-ATRI-Signature: sha256=<hmac>` header when secret is configured.
- HTTP delivery errors are captured and returned as structured results; no exception propagation.

**Implementation:**

- `src/atri/core/services/notification.py` - `WebhookConfig`, `WebhookDeliveryResult`, `WebhookNotificationService` with HMAC signing and httpx delivery.
- `src/atri/api/routes/notifications.py` - 4 endpoints registered under `/api/v1/notifications`.
- `tests/test_notification.py` - 12 unit + integration tests covering delivery, HMAC, errors, and 404 paths.

---

### 15. Observability (Metrics + Structured Logging) - IMPLEMENTED

**Goal:** Enable SRE-style production operation with Prometheus scraping and structured JSON request logs.

**Status:** Complete.

**Acceptance criteria:**

- `GET /metrics` returns Prometheus text exposition format with `atri_requests_total` counter and `atri_request_duration_seconds` summary.
- Every HTTP request emits one JSON log line with `method`, `path`, `status_code`, `duration_ms`, and `tenant_id`.
- `ObservabilityMiddleware` is registered in the FastAPI app; metrics are accumulated in-process.
- Registry is thread-safe; resets cleanly for tests.

**Implementation:**

- `src/atri/core/services/metrics.py` - `MetricsRegistry` with thread-safe counter/histogram; `to_text_format()` for Prometheus output; module-level `registry` singleton.
- `src/atri/api/routes/observability.py` - `GET /metrics` endpoint + `ObservabilityMiddleware`.
- `tests/test_metrics.py` - 9 tests covering counter operations, histogram percentiles, text format, and the `/metrics` HTTP endpoint.
