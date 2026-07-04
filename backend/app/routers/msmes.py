"""MSME + what-if routers."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.database import loads, session_scope
from app.db.models import MSME
from app.scoring.metrics import compute_metrics

router = APIRouter(prefix="/api", tags=["msmes"])


class WhatIfRequest(BaseModel):
    revenue_delta: float = 0.0


def _msme_summary(m: MSME) -> dict[str, Any]:
    return {
        "id": m.id, "name": m.name, "sector": m.sector, "sub_sector": m.sub_sector,
        "udyam_number": m.udyam_number, "gstin": m.gstin, "city": m.city, "state": m.state,
        "vintage_years": m.vintage_years, "entity_type": m.entity_type,
        "annual_turnover_lakh": m.annual_turnover_lakh, "is_near_miss": bool(m.is_near_miss),
        "profile": loads(m.profile_json) if m.profile_json else {},
    }


@router.get("/msmes")
def list_msmes() -> dict[str, Any]:
    with session_scope() as s:
        rows = s.query(MSME).order_by(MSME.id).all()
        return {"msmes": [_msme_summary(m) for m in rows]}


@router.get("/msmes/{msme_id}")
def get_msme(msme_id: str) -> dict[str, Any]:
    with session_scope() as s:
        m = s.get(MSME, msme_id)
        if not m:
            raise HTTPException(404, "MSME not found")
        txns = [{"date": t.date, "category": t.category, "amount": t.amount,
                 "description": t.description, "channel": t.channel} for t in m.transactions]
        invs = [{"invoice_number": i.invoice_number, "invoice_date": i.invoice_date,
                 "invoice_total": i.invoice_total, "filing_status": i.filing_status} for i in m.invoices]
        msme = _msme_summary(m)
        metrics = compute_metrics(msme, txns, invs)
        return {"msme": msme, "transaction_count": len(txns), "invoice_count": len(invs),
                "metrics": metrics, "recent_transactions": txns[-15:]}


@router.post("/msmes/{msme_id}/what-if")
def what_if(msme_id: str, body: WhatIfRequest) -> dict[str, Any]:
    """Deterministic-only recompute with a revenue delta (no LLM). Fast."""
    if not -0.5 <= body.revenue_delta <= 0.5:
        raise HTTPException(400, "revenue_delta must be within ±0.5")
    with session_scope() as s:
        m = s.get(MSME, msme_id)
        if not m:
            raise HTTPException(404, "MSME not found")
        txns = [{"date": t.date, "category": t.category, "amount": t.amount,
                 "description": t.description, "channel": t.channel} for t in m.transactions]
        invs = [{"invoice_number": i.invoice_number, "invoice_date": i.invoice_date,
                 "invoice_total": i.invoice_total, "filing_status": i.filing_status} for i in m.invoices]
        msme = _msme_summary(m)
        metrics = compute_metrics(msme, txns, invs, revenue_delta=body.revenue_delta)
        return {"msme_id": msme_id, "revenue_delta": body.revenue_delta, "metrics": metrics}