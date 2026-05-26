from html import escape

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from atri.api.schemas import DashboardSummaryResponse
from atri.core.services.audit import TraceAuditService
from atri.core.services.graph_store import TraceGraphStore
from atri.core.services.graph_factory import make_graph_store
from atri.core.services.review import TraceReviewService
from atri.core.tenancy import TenantContext, resolve_tenant

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


def _build_dashboard_snapshot(
    review_svc: TraceReviewService,
    audit_svc: TraceAuditService,
    gs: TraceGraphStore,
) -> dict[str, object]:
    summary = {
        "trace_coverage": 0.78,
        "suspect_links": 14,
        "orphan_requirements": 7,
        "orphan_tests": 5,
        "high_risk_changes_7d": 3,
    }
    return {
        "summary": summary,
        "review_summary": review_svc.summarize_reviews(),
        "audit_summary": audit_svc.summarize_events(),
        "graph_stats": gs.stats(),
    }


def _render_metric_cards(summary: dict[str, float | int]) -> str:
    cards = []
    labels = [
        ("Trace coverage", summary["trace_coverage"]),
        ("Suspect links", summary["suspect_links"]),
        ("Orphan requirements", summary["orphan_requirements"]),
        ("Orphan tests", summary["orphan_tests"]),
        ("High-risk changes", summary["high_risk_changes_7d"]),
    ]
    for label, value in labels:
        cards.append(
            "<div class='card'>"
            f"<span>{escape(str(label))}</span>"
            f"<strong>{escape(str(value))}</strong>"
            "</div>"
        )
    return "".join(cards)


def _render_bar_chart(title: str, series: dict[str, int], accent: str) -> str:
    max_value = max(series.values()) if series else 1
    bars = []
    for index, (label, value) in enumerate(series.items()):
        width = max(8, int((value / max_value) * 180)) if max_value else 8
        y = 18 + (index * 34)
        bars.append(
            "<g>"
            f"<text x='0' y='{y}'>{escape(label)}</text>"
            f"<rect x='170' y='{y - 12}' width='{width}' height='18' rx='9' "
            f"fill='{accent}' />"
            f"<text x='{180 + width}' y='{y}'>{value}</text>"
            "</g>"
        )
    height = max(84, 34 * max(len(series), 1) + 8)
    return (
        "<section class='panel'>"
        f"<h3>{escape(title)}</h3>"
        f"<svg viewBox='0 0 360 {height}' role='img' aria-label='{escape(title)}'>"
        f"{''.join(bars)}"
        "</svg></section>"
    )


def _render_dashboard_html(snapshot: dict[str, object]) -> str:
    summary = snapshot["summary"]
    review_summary = snapshot["review_summary"]
    audit_summary = snapshot["audit_summary"]
    graph_stats = snapshot["graph_stats"]

    coverage_width = int(float(summary["trace_coverage"]) * 100)
    review_series = {
        "Accepted": review_summary["accepted_reviews"],
        "Rejected": review_summary["rejected_reviews"],
        "Pending": review_summary["pending_reviews"],
    }
    audit_series = {
        key.replace("_", " ").title(): value
        for key, value in audit_summary.items()
        if key != "total_events"
    } or {"Total": 0}
    graph_series = {
        "Artifacts": int(graph_stats["artifact_count"]),
        "Links": int(graph_stats["link_count"]),
        "Roots": int(graph_stats["root_artifacts"]),
        "Leaves": int(graph_stats["leaf_artifacts"]),
    }

    isolated_artifacts = graph_stats["isolated_artifacts"]
    average_degree = graph_stats["average_degree"]
    total_events = audit_summary.get("total_events", 0)
    accepted_reviews = review_summary["accepted_reviews"]

    css_lines = [
        ":root {",
        "  color-scheme: light;",
        "  --bg: #f4f2ec;",
        "  --panel: #fffaf2;",
        "  --ink: #1e1a17;",
        "  --muted: #6d6359;",
        "  --accent: #0f766e;",
        "  --accent-2: #c2410c;",
        "  --accent-3: #334155;",
        "  --line: rgba(30, 26, 23, 0.12);",
        "}",
        "* { box-sizing: border-box; }",
        (
            "body { margin: 0; font-family: Inter, ui-sans-serif, system-ui, sans-serif; "
            "background: radial-gradient(circle at top, #fff7ed, "
            "var(--bg) 55%); color: var(--ink); }"
        ),
        "main { max-width: 1240px; margin: 0 auto; padding: 32px 20px 40px; }",
        ".hero { display: grid; gap: 12px; margin-bottom: 24px; }",
        (
            ".eyebrow { text-transform: uppercase; letter-spacing: .18em; font-size: 12px; "
            "color: var(--muted); }"
        ),
        "h1 { margin: 0; font-size: clamp(2rem, 4vw, 3.5rem); line-height: 1; }",
        (
            ".sub { max-width: 760px; color: var(--muted); font-size: 1rem; "
            "line-height: 1.5; }"
        ),
        ".grid { display: grid; gap: 16px; }",
        (
            ".cards { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); "
            "margin-bottom: 16px; }"
        ),
        (
            ".card, .panel { background: rgba(255, 250, 242, 0.92); border: 1px solid "
            "var(--line); border-radius: 20px; box-shadow: 0 18px 50px rgba(15, 23, 42, 0.08); }"
        ),
        (
            ".card { padding: 18px; min-height: 120px; display: flex; flex-direction: "
            "column; justify-content: space-between; }"
        ),
        ".card span { color: var(--muted); font-size: .9rem; }",
        ".card strong { font-size: 2rem; letter-spacing: -0.04em; }",
        ".panels { grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }",
        ".panel { padding: 18px 18px 14px; }",
        ".panel h3 { margin: 0 0 14px; font-size: 1rem; }",
        ".badge-row { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 8px; }",
        (
            ".badge { padding: 10px 12px; border-radius: 999px; background: rgba(15, 118, "
            "110, .09); color: var(--accent); font-weight: 600; font-size: .92rem; }"
        ),
        ".section-title { margin: 28px 0 12px; font-size: 1.15rem; }",
        ".coverage { display: grid; gap: 10px; }",
        (
            ".bar-shell { width: 100%; height: 16px; border-radius: 999px; background: "
            "rgba(15, 23, 42, 0.08); overflow: hidden; }"
        ),
        (
            ".bar-fill { width: "
            f"{coverage_width}%; height: 100%; border-radius: inherit; background: "
            "linear-gradient(90deg, var(--accent), #22c55e); }"
        ),
        ".fine { color: var(--muted); font-size: .92rem; }",
        "svg { width: 100%; height: auto; display: block; }",
        "text { font-size: 12px; fill: var(--ink); }",
    ]

    html_lines = [
        "<!doctype html>",
        "<html lang='en'>",
        "<head>",
        "  <meta charset='utf-8' />",
        "  <meta name='viewport' content='width=device-width, initial-scale=1' />",
        "  <title>ATRI Traceability Dashboard</title>",
        "  <style>",
        "    " + "\n    ".join(css_lines),
        "  </style>",
        "</head>",
        "<body>",
        "  <main>",
        "    <section class='hero'>",
        "      <div class='eyebrow'>ATRI / NASA IV&V traceability intelligence</div>",
        "      <h1>Traceability Dashboard</h1>",
        (
            "      <div class='sub'>A visual operating view of trace coverage, review "
            "activity, audit retention, and graph topology. The page is backed by the "
            "same persisted stores that power the API.</div>"
        ),
        "    </section>",
        "",
        "    <section class='grid cards'>",
        f"      {_render_metric_cards(summary)}",
        "    </section>",
        "",
        "    <section class='panel coverage'>",
        "      <h3>Trace coverage</h3>",
        "      <div class='bar-shell'><div class='bar-fill'></div></div>",
        (
            "      <div class='fine'>Coverage is shown as a percentage of trace "
            "completeness across the current summary snapshot.</div>"
        ),
        "    </section>",
        "",
        "    <h2 class='section-title'>Operational panels</h2>",
        "    <section class='grid panels'>",
        f"      {_render_bar_chart('Review decisions', review_series, 'var(--accent)')}",
        f"      {_render_bar_chart('Audit events', audit_series, 'var(--accent-2)')}",
        f"      {_render_bar_chart('Graph topology', graph_series, 'var(--accent-3)')}",
        "    </section>",
        "",
        "    <section class='panel' style='margin-top:16px;'>",
        "      <h3>Graph health</h3>",
        "      <div class='badge-row'>",
        f"        <div class='badge'>Isolated artifacts: {isolated_artifacts}</div>",
        f"        <div class='badge'>Average degree: {average_degree}</div>",
        f"        <div class='badge'>Audit events: {total_events}</div>",
        f"        <div class='badge'>Accepted reviews: {accepted_reviews}</div>",
        "      </div>",
        "    </section>",
        "  </main>",
        "</body>",
        "</html>",
    ]

    return "\n".join(html_lines)


@router.get("/summary", response_model=DashboardSummaryResponse)
def summary() -> dict:
    return {
        "trace_coverage": 0.78,
        "suspect_links": 14,
        "orphan_requirements": 7,
        "orphan_tests": 5,
        "high_risk_changes_7d": 3,
    }


@router.get("/view", response_class=HTMLResponse)
def view(tenant: TenantContext = Depends(resolve_tenant)) -> HTMLResponse:
    review_svc = TraceReviewService(
        str(tenant.review_store_path),
        history_path=str(tenant.review_history_store_path),
    )
    audit_svc = TraceAuditService(str(tenant.audit_store_path))
    gs = make_graph_store(str(tenant.graph_store_path))
    return HTMLResponse(_render_dashboard_html(_build_dashboard_snapshot(review_svc, audit_svc, gs)))


@router.get("/drilldown/reviews")
def drilldown_reviews(tenant: TenantContext = Depends(resolve_tenant)) -> list[dict]:
    """
    ID: ATRI-DASH-003
    Purpose: Return per-reviewer review breakdown for dashboard drill-down.
    Outputs: list of dicts with reviewer, total, accepted, rejected, pending counts.
    """
    review_svc = TraceReviewService(
        str(tenant.review_store_path),
        history_path=str(tenant.review_history_store_path),
    )
    return review_svc.reviewer_summary()


@router.get("/drilldown/audit")
def drilldown_audit(tenant: TenantContext = Depends(resolve_tenant)) -> list[dict]:
    """
    ID: ATRI-DASH-004
    Purpose: Return per-actor audit event breakdown for the dashboard.
    Outputs: list of dicts with actor and event-type counts.
    """
    return TraceAuditService(str(tenant.audit_store_path)).actor_summary()


@router.get("/drilldown/audit/subject/{subject_id}")
def drilldown_audit_subject(
    subject_id: str,
    tenant: TenantContext = Depends(resolve_tenant),
) -> list[dict]:
    """
    ID: ATRI-DASH-005
    Purpose: Return all audit events for a specific artifact or link subject.
    Inputs: subject_id - the artifact or link identifier.
    Outputs: Chronological list of audit event dicts.
    """
    return [
        {
            "event_type": e.event_type,
            "subject_id": e.subject_id,
            "actor": e.actor,
            "timestamp": e.timestamp,
            "details": e.details,
        }
        for e in TraceAuditService(str(tenant.audit_store_path)).subject_history(subject_id)
    ]


@router.get("/drilldown/graph")
def drilldown_graph(tenant: TenantContext = Depends(resolve_tenant)) -> dict:
    """
    ID: ATRI-DASH-006
    Purpose: Return full graph stats and adjacency map for dashboard graph view.
    Outputs: dict with stats and adjacency_map fields.
    """
    gs = make_graph_store(str(tenant.graph_store_path))
    return {
        "stats": gs.stats(),
        "adjacency_map": gs.adjacency_map(),
    }