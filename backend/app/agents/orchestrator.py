"""Pipeline orchestrator — runs the agent DAG in parallel layers, streams SSE
events, persists each agent output + the final report to SQLite for replay.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable

from app.agents.base import AgentContext, run_agent
from app.agents.definitions import AGENTS, DAG_LAYERS
from app.db.database import dumps, session_scope
from app.db.models import AgentOutput, Run
from app.scoring.metrics import compute_metrics

Emit = Callable[[dict[str, Any]], Awaitable[None]]


def _load_data(msme_obj) -> tuple[dict, list[dict], list[dict]]:
    msme = {
        "id": msme_obj.id, "name": msme_obj.name, "sector": msme_obj.sector,
        "sub_sector": msme_obj.sub_sector, "udyam_number": msme_obj.udyam_number,
        "gstin": msme_obj.gstin, "city": msme_obj.city, "state": msme_obj.state,
        "vintage_years": msme_obj.vintage_years, "entity_type": msme_obj.entity_type,
        "annual_turnover_lakh": msme_obj.annual_turnover_lakh,
        "is_near_miss": bool(msme_obj.is_near_miss),
        "profile": __import__("json").loads(msme_obj.profile_json) if msme_obj.profile_json else {},
    }
    txns = [{"date": t.date, "description": t.description, "category": t.category,
             "amount": t.amount, "channel": t.channel, "counterparty": t.counterparty}
            for t in msme_obj.transactions]
    invs = [{"invoice_number": i.invoice_number, "invoice_date": i.invoice_date,
             "party_gstin": i.party_gstin, "party_name": i.party_name,
             "taxable_value": i.taxable_value, "gst_amount": i.gst_amount,
             "invoice_total": i.invoice_total, "filing_status": i.filing_status}
            for i in msme_obj.invoices]
    return msme, txns, invs


async def run_pipeline(
    run_id: str,
    msme_obj,
    what_if: dict[str, Any],
    emit: Emit,
    offline: bool,
) -> dict[str, Any]:
    started = time.time()
    msme, txns, invs = _load_data(msme_obj)
    revenue_delta = float((what_if or {}).get("revenue_delta", 0.0))
    metrics = compute_metrics(msme, txns, invs, revenue_delta=revenue_delta)

    await emit({"type": "pipeline_start", "run_id": run_id, "msme_id": msme["id"],
                "msme_name": msme["name"], "offline": offline,
                "metrics_ready": True, "health_score": metrics["health_score"],
                "loan_readiness": metrics["loan_readiness"]})
    await emit({"type": "metrics", "run_id": run_id, "metrics": metrics})

    prior: dict[str, dict[str, Any]] = {}
    for li, layer in enumerate(DAG_LAYERS):
        await emit({"type": "layer_start", "layer": li, "agents": layer})
        ctx = AgentContext(msme=msme, transactions=txns, invoices=invs, metrics=metrics,
                           prior_outputs=prior, what_if=what_if, offline=offline)

        async def _run_one(key: str) -> tuple[str, dict[str, Any]]:
            agent = AGENTS[key]
            out = await run_agent(agent, ctx, emit)
            return key, out

        results = await asyncio.gather(*[_run_one(k) for k in layer], return_exceptions=False)
        for key, out in results:
            prior[key] = out
            _persist_agent(run_id, key, li, out)
        await emit({"type": "layer_done", "layer": li, "agents": layer})

    report = prior.get("report", {})
    elapsed = round(time.time() - started, 2)
    await emit({"type": "pipeline_done", "run_id": run_id, "elapsed_s": elapsed,
                "health_score": metrics["health_score"], "loan_readiness": metrics["loan_readiness"]})

    _finalize_run(run_id, metrics, report, offline, what_if)
    return {"run_id": run_id, "metrics": metrics, "report": report, "offline": offline, "elapsed_s": elapsed}


def _persist_agent(run_id: str, key: str, layer: int, out: dict[str, Any]) -> None:
    try:
        with session_scope() as s:
            s.add(AgentOutput(run_id=run_id, agent_key=key, layer=layer, output_json=dumps(out)))
    except Exception:
        pass


def _finalize_run(run_id: str, metrics: dict, report: dict, offline: bool, what_if: dict) -> None:
    from datetime import datetime, timezone
    try:
        with session_scope() as s:
            r = s.get(Run, run_id)
            if r is None:
                r = Run(id=run_id, msme_id=metrics.get("msme_id", ""), status="running",
                        offline=int(offline), what_if_json=dumps(what_if or {}))
                s.add(r)
                s.flush()
                r = s.get(Run, run_id)
            r.metrics_json = dumps(metrics)
            r.report_json = dumps(report)
            r.status = "done"
            r.offline = int(offline)
            r.finished_at = datetime.now(timezone.utc)
    except Exception:
        pass