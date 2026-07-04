"""ULI / OCEN ecosystem surface (Problem Statement 3).

Exposes UdyamMitra's financial-health score through spec-shaped endpoints that
map to the RBI Unified Lending Interface (ULI) and the Open Credit Enablement
Network (OCEN). These endpoints are **spec-ready, not yet live** — they return
HTTP 501 with an honest `live: false` marker until the ULI/OCEN schemas are
finalised and a lending partner is wired. We do not fake live integration.

AA (Account Aggregator) is on the ingestion side (see app.connectors.aa) and
is not exposed here.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/ecosystem", tags=["ecosystem"])


def _spec_ready(stage: str, detail: str) -> dict[str, Any]:
    return {
        "status": "spec_ready",
        "live": False,
        "stage": stage,
        "detail": detail,
    }


@router.get("/uli/health-card/{msme_id}")
def uli_health_card(msme_id: str) -> dict[str, Any]:
    """ULI-shaped health-card fetch (lender-side).

    Designed to return the multidimensional health score + sub-scores + cash-
    flow forecast in the ULI payload schema. Returns 501 until the ULI spec is
    finalised and a lender endpoint is registered.
    """
    raise HTTPException(
        status_code=501,
        detail=_spec_ready(
            "uli",
            "ULI endpoint is spec-ready; not yet registered with a ULI node. "
            "The health-card payload maps to app.scoring.metrics.compute_metrics.",
        ),
    )


@router.get("/ocen/signal/{msme_id}")
def ocen_signal(msme_id: str, product: str = Query("od_cc", description="OCEN loan product id")) -> dict[str, Any]:
    """OCEN-shaped credit signal for loan origination.

    Designed to return an OCEN signal (health score, recommended product, OD/CC
    limit, scheme eligibility) for the requested product. Returns 501 until an
    OCEN loan-origination partner is wired.
    """
    raise HTTPException(
        status_code=501,
        detail=_spec_ready(
            "ocen",
            f"OCEN signal for product='{product}' is spec-ready; not yet wired "
            "to an OCEN origination partner.",
        ),
    )


@router.get("/status")
def ecosystem_status() -> dict[str, Any]:
    """Honest summary of which ecosystem surfaces are live vs spec-ready."""
    return {
        "uli": {"live": False, "stage": "spec_ready"},
        "ocen": {"live": False, "stage": "spec_ready"},
        "aa_ingestion": {"live": False, "stage": "spec_ready"},
        "note": "No live ULI/OCEN/AA integration is claimed. Connectors are "
                "spec-ready stubs; see app/connectors/ and infra/cdk/.",
    }