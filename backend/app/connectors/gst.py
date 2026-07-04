"""GST connector — GSTR-2A/2B (supplier reconciliation) + 3B via a GSP/ASP.

Live pull requires a GSP/ASP partner (ClearTax / Masterso / TaxPro). Until
GSP_ASP_BASE_URL + GSP_ASP_TOKEN are configured, `fetch` raises
NotImplementedError — the app then falls back to seeded GST invoice data.
"""
from __future__ import annotations

from app.connectors.base import ConnectorResult, _utcnow_iso
from app.core.config import settings


class GSTConnector:
    source = "gst"

    def fetch(self, msme_id: str, gstin: str | None = None) -> ConnectorResult:
        base = (settings.gsp_asp_base_url or "").strip()
        token = (settings.gsp_asp_token or "").strip()
        if not base or not token:
            raise NotImplementedError(
                "GST live pull is spec-ready but not wired: set GSP_ASP_BASE_URL "
                "and GSP_ASP_TOKEN (via AWS Secrets Manager in prod). Falling "
                "back to seeded GST invoice data."
            )
        # When wired: authenticate with the GSP/ASP, call GSTN for GSTR-2B
        # (reconciled supplier invoices) + GSTR-3B (filed returns), normalise
        # into the same record shape as app.db.models.GSTInvoice, persist raw
        # JSON to S3 and structured rows to Aurora. Left as the integration
        # step so the scoring core's gst_consistency metric keeps its meaning.
        raise NotImplementedError("GST live fetch path not yet implemented.")