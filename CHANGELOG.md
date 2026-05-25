# Changelog

## Unreleased

### Added

- Persisted trace graph adapter with graph sync support and impact analysis fallback to stored links.
- File-backed persistence for analyst review decisions under the processed data directory.
- Analyst review workflow endpoints for accepting and rejecting suggested trace links.
- Capability catalog endpoint that advertises the expanded ATRI scope.
- Roadmap documentation for ingestion, semantic analysis, graph storage, analyst review, and dashboards.
- Shared API response schemas for health, dashboard, traceability, impact, and gap endpoints.
- OpenAPI metadata on the FastAPI application so the service advertises its version and purpose.
- Contract tests for the core API routes to keep the scaffold aligned with its documented behavior.

## 2026-05-25

### Added

- Initial API contract hardening for the ATRI scaffold.