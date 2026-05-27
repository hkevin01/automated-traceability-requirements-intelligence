"""
ID: ATRI-RPT-ROUTE-001
Purpose: Compliance report API routes - JSON summary and CSV downloads.
Requirement: Provide exportable compliance evidence packages from audit + review data.
Inputs: tenant context via Depends(resolve_tenant).
Outputs: JSON or CSV HTTP responses.
References: ATRI Epic 13.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from atri.core.services.compliance_report import ComplianceReportService
from atri.core.tenancy import TenantContext, resolve_tenant

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def _make_service(tenant: TenantContext) -> ComplianceReportService:
    """
    ID: ATRI-RPT-ROUTE-002
    Purpose: Construct ComplianceReportService from tenant-scoped storage paths.
    """
    return ComplianceReportService(
        audit_store_path=tenant.audit_store_path,
        review_store_path=tenant.review_store_path,
        review_history_path=tenant.review_history_store_path,
    )


@router.get("/compliance", summary="JSON compliance report")
async def get_compliance_report(tenant: TenantContext = Depends(resolve_tenant)):
    """
    ID: ATRI-RPT-ROUTE-003
    Purpose: Return JSON compliance summary (audit + review stats).
    Outputs: JSON dict with summary statistics.
    """
    svc = _make_service(tenant)
    report = svc.build()
    return report.to_dict()


@router.get("/compliance/audit.csv", summary="Audit events CSV download")
async def get_audit_csv(tenant: TenantContext = Depends(resolve_tenant)):
    """
    ID: ATRI-RPT-ROUTE-004
    Purpose: Download audit events as a CSV file attachment.
    Outputs: text/csv response with Content-Disposition attachment header.
    """
    svc = _make_service(tenant)
    report = svc.build()
    csv_data = report.to_audit_csv()
    return PlainTextResponse(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_events.csv"},
    )


@router.get("/compliance/reviews.csv", summary="Reviews CSV download")
async def get_reviews_csv(tenant: TenantContext = Depends(resolve_tenant)):
    """
    ID: ATRI-RPT-ROUTE-005
    Purpose: Download review records as a CSV file attachment.
    Outputs: text/csv response with Content-Disposition attachment header.
    """
    svc = _make_service(tenant)
    report = svc.build()
    csv_data = report.to_review_csv()
    return PlainTextResponse(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=reviews.csv"},
    )
