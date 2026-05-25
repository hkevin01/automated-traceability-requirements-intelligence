# ATRI Architecture

## 1. Context

ATRI supports continuous traceability intelligence across requirements, design, code, and tests for high-assurance environments.

## 2. Logical Components

- Ingestion Pipeline
  - Parses requirement specs, design docs, code metadata, and test metadata.
- Normalization Layer
  - Converts artifacts into canonical forms and stable IDs.
- Traceability Intelligence Engine
  - Link suggestion service (NLP/LLM + rules)
  - Impact analysis service (graph expansion + risk scoring)
  - Gap detection service (coverage, orphan, and stale-link checks)
- Evidence Store
  - Stores links, confidence, rationale, provenance, and review outcomes.
- API + Dashboard Feed
  - Serves operational views and analyst workflows.

## 3. Data Model (Core)

- Artifact(id, type, title, body, version, source)
- Link(id, source_artifact_id, target_artifact_id, link_type, confidence, status)
- ChangeEvent(id, artifact_id, change_type, timestamp, author)
- ImpactResult(id, change_event_id, impacted_artifact_id, score, rationale)
- GapFinding(id, artifact_id, finding_type, severity, rationale)

## 4. Key Workflows

1. Requirement Link Suggestion
   - Input requirement -> candidate retrieval -> rule/LLM scoring -> ranked suggestions.
2. Change Impact Analysis
   - Changed artifact -> graph traversal by dependency/link types -> impacted set + risk score.
3. Gap Detection
   - Coverage rules + graph checks -> identify missing tests, weak links, orphan artifacts.
4. Dashboard Refresh
   - KPI computation -> endpoint payload for near-real-time visualizations.

## 5. Safety-Critical Guardrails

- Human-in-the-loop acceptance before link finalization.
- Full audit trail for model outputs and reviewer decisions.
- Deterministic fallback rules when model confidence is below threshold.
- Baseline snapshots and diff history for every artifact version.

## 6. Deployment Modes

- Local Dev: FastAPI + in-memory graph abstraction.
- Team Mode: FastAPI + Postgres + Neo4j + Redis cache.
- Enterprise Mode: event bus, model registry, policy engine, SSO.
