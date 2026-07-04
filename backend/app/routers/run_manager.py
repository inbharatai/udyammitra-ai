"""In-memory run manager: per-run event queues for live SSE streaming.

POST /api/runs schedules the pipeline as a background asyncio task that pushes
events into a per-run queue; the SSE endpoint tails the queue (after replaying
any already-logged events). Completed runs are replayed from SQLite events_json.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.agents.orchestrator import run_pipeline
from app.core.config import settings
from app.db.database import dumps, loads, session_scope
from app.db.models import MSME, Run


class _RunState:
    def __init__(self) -> None:
        self.queue: asyncio.Queue = asyncio.Queue()
        self.events: list[dict[str, Any]] = []
        self.status: str = "running"
        self.task: asyncio.Task | None = None
        self.msme_id: str | None = None


class RunManager:
    def __init__(self) -> None:
        self.runs: dict[str, _RunState] = {}

    def create_run(self, msme_id: str, what_if: dict[str, Any] | None) -> str:
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        offline = settings.offline_mode
        # create DB row
        with session_scope() as s:
            s.add(Run(id=run_id, msme_id=msme_id, status="running",
                      offline=int(offline), what_if_json=dumps(what_if or {})))
        state = _RunState()
        state.msme_id = msme_id
        self.runs[run_id] = state
        state.task = asyncio.create_task(self._execute(run_id, msme_id, what_if or {}, offline, state))
        return run_id

    async def _execute(self, run_id: str, msme_id: str, what_if: dict, offline: bool, state: _RunState) -> None:
        async def emit(ev: dict[str, Any]) -> None:
            ev = {**ev, "ts": datetime.now(timezone.utc).isoformat()}
            state.events.append(ev)
            try:
                state.queue.put_nowait(ev)
            except asyncio.QueueFull:
                pass

        try:
            with session_scope() as s:
                msme = s.get(MSME, msme_id)
                if msme is None:
                    raise ValueError(f"MSME {msme_id} not found")
                # force-load relationships while session open
                _ = list(msme.transactions), list(msme.invoices)
                msme_obj = msme
                # detach into plain access by reading now
                await run_pipeline(run_id, msme_obj, what_if, emit, offline)
        except Exception as e:  # noqa: BLE001
            state.status = "failed"
            await emit({"type": "pipeline_failed", "run_id": run_id, "error": str(e)})
            with session_scope() as s:
                r = s.get(Run, run_id)
                if r:
                    r.status = "failed"
        else:
            state.status = "done"
        # persist full event log for cross-restart replay
        try:
            with session_scope() as s:
                r = s.get(Run, run_id)
                if r:
                    r.events_json = dumps(state.events)
                    if r.status != "failed":
                        r.status = "done"
        except Exception:
            pass
        # signal end-of-stream to any waiting SSE consumer
        try:
            state.queue.put_nowait({"type": "__end__", "status": state.status})
        except asyncio.QueueFull:
            pass

    async def stream(self, run_id: str):
        """Async generator of event dicts (for SSE). Replays then tails."""
        state = self.runs.get(run_id)
        if state is not None:
            # replay already-logged events
            for ev in list(state.events):
                yield ev
            # tail
            while True:
                ev = await state.queue.get()
                if ev.get("type") == "__end__":
                    yield {"type": "pipeline_end", "status": ev.get("status")}
                    break
                yield ev
        else:
            # run not active — replay from DB if exists
            with session_scope() as s:
                r = s.get(Run, run_id)
                if r and r.events_json:
                    for ev in loads(r.events_json):
                        yield ev
                    yield {"type": "pipeline_end", "status": r.status, "replayed": True}
                else:
                    yield {"type": "pipeline_end", "status": "not_found"}

    def status(self, run_id: str) -> dict[str, Any]:
        state = self.runs.get(run_id)
        if state:
            return {"run_id": run_id, "status": state.status, "live": True,
                    "msme_id": state.msme_id}
        with session_scope() as s:
            r = s.get(Run, run_id)
            if r:
                return {"run_id": run_id, "status": r.status, "live": False,
                        "msme_id": r.msme_id, "offline": bool(r.offline)}
        return {"run_id": run_id, "status": "not_found"}


run_manager = RunManager()