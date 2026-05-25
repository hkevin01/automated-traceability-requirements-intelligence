# Automated Traceability & Requirements Intelligence (ATRI)

ATRI is a mission-oriented scaffold for AI-assisted requirements traceability, automated change-impact analysis, intelligent gap detection, and real-time traceability dashboards.

The architecture is aligned to the needs of safety-critical software assurance practices like those used in NASA IV&V programs: requirements rigor, independent analysis, risk awareness, and end-to-end traceability from requirement -> design -> code -> test.

## Why This Project

Traditional traceability work is labor-intensive. ATRI is designed to reduce analyst hours while increasing review coverage through:

- AI-assisted requirement linking
- Automated impact analysis for upstream/downstream changes
- Gap detection across lifecycle artifacts
- Real-time dashboard APIs for coverage and risk posture

## Expanded Capability Map

- AI-assisted requirement linking across requirements, design, code, tests, hazards, and interfaces
- Automated change-impact analysis for affected design, code, test, hazard, and verification artifacts
- Intelligent gap detection for orphan requirements, missing tests, weak mitigations, and incomplete verification
- Analyst review workflow for accepting and rejecting suggested trace links
- Persisted trace graph for replayable impact analysis across stored links
- Audit trail for review and graph sync actions
- Real-time traceability dashboards for coverage, volatility, change activity, and risk posture

## Initial Architecture

- API Layer (FastAPI): endpoints for requirements, links, impact, and gap analysis
- Intelligence Layer: services for semantic linking, impact graph traversal, and gap heuristics
- Traceability Graph: graph model abstraction for requirement/design/code/test relationships
- Dashboard Feed: lightweight summary endpoint suitable for real-time frontends
- Compliance Mapping: hooks to map evidence to standards and IV&V-style checkpoints

See docs in `docs/` for detailed architecture and IV&V alignment.

## Quick Start

1. Create and activate a Python 3.11+ virtual environment.
2. Copy `.env.example` to `.env` and set values.
3. Install dependencies:
   - `make install`
4. Run API locally:
   - `make dev`
5. Run tests:
   - `make test`

## API Preview

- `GET /health` - service health
- `GET /api/v1/dashboard/summary` - high-level traceability KPIs
- `POST /api/v1/traceability/link-suggest` - suggest links for a requirement
- `POST /api/v1/traceability/review` - accept or reject a suggested trace link
- `GET /api/v1/traceability/reviews` - list review decisions
- `GET /api/v1/traceability/reviews/summary` - review counts by status
- `POST /api/v1/traceability/graph` - persist artifacts and trace links for impact analysis
- `GET /api/v1/traceability/audit/events` - list audit events for traceability actions
- `GET /api/v1/traceability/audit/summary` - count audit events by type
- `POST /api/v1/impact/analyze` - impact analysis from changed artifacts
- `POST /api/v1/gaps/detect` - detect missing or weak trace links

## Repository Layout

- `src/atri/` - application code
- `tests/` - test suite
- `docs/` - architecture and process docs
- `docker/` - container scaffolding
- `scripts/` - utility scripts

## Near-Term Roadmap

- Build ingestion adapters for DOORS, Jama, Visure, Word/PDF, and SysML sources
- Integrate vector retrieval for semantic linking
- Add graph database adapter (Neo4j)
- Add authn/authz, review state, and audit events
- Expand the review workflow with persistence and reviewer assignment
- Add a true graph database backend behind the trace graph store adapter
- Persist audit events to an immutable backend and expose reviewer history drill-downs
- Ship frontend dashboard (React) connected to summary, capability, and drill-down APIs
