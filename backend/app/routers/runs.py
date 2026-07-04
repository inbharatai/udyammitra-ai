"""Run routers: kick pipeline, live SSE stream, status, report."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.db.database import loads, session_scope
from app.db.models import Run
from app.routers.run_manager import run_manager

router = APIRouter(prefix="/api", tags=["runs"])


class RunCreate(BaseModel):
    msme_id: str
    what_if: dict[str, Any] | None = None


@router.post("/runs")
async def create_run(body: RunCreate) -> dict[str, Any]:
    # validate msme exists
    with session_scope() as s:
        from app.db.models import MSME
        if not s.get(MSME, body.msme_id):
            raise HTTPException(404, "MSME not found")
    run_id = run_manager.create_run(body.msme_id, body.what_if)
    return {"run_id": run_id, "stream": f"/api/runs/{run_id}/events",
            "status": f"/api/runs/{run_id}/status", "offline": _is_offline()}


@router.get("/runs/{run_id}/events")
async def stream_events(run_id: str):
    async def gen():
        async for ev in run_manager.stream(run_id):
            yield f"data: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"
            await asyncio.sleep(0)  # flush
        yield "data: {\"type\": \"__closed__\"}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                                      "Connection": "keep-alive"})


@router.get("/runs/{run_id}/status")
def status(run_id: str) -> dict[str, Any]:
    return run_manager.status(run_id)


@router.get("/runs/{run_id}/report")
def report(run_id: str) -> dict[str, Any]:
    with session_scope() as s:
        r = s.get(Run, run_id)
        if not r:
            raise HTTPException(404, "Run not found")
        return {
            "run_id": run_id, "msme_id": r.msme_id, "status": r.status,
            "offline": bool(r.offline), "metrics": loads(r.metrics_json) if r.metrics_json else None,
            "report": loads(r.report_json) if r.report_json else None,
        }


@router.get("/runs")
def list_runs(limit: int = 20) -> dict[str, Any]:
    with session_scope() as s:
        rows = s.query(Run).order_by(Run.started_at.desc()).limit(limit).all()
        return {"runs": [{"run_id": r.id, "msme_id": r.msme_id, "status": r.status,
                          "offline": bool(r.offline), "started_at": r.started_at.isoformat() if r.started_at else None,
                          "health_score": (loads(r.metrics_json) or {}).get("health_score") if r.metrics_json else None}
                         for r in rows]}


def _is_offline() -> bool:
    from app.core.config import settings
    return settings.offline_mode