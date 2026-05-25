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