"""AgentRun wrapper + tool-calling execution loop.

Discipline of a framework (~160 LOC) without the dependency:
  * system prompt, tool subset, Pydantic I/O schema, max_iterations, timeout
  * bounded schema-validation repair (1 retry) -> deterministic fallback stub
  * per-agent context budget (agents receive summaries, not raw ledgers)
  * offline mode: agents run their deterministic fallback with zero network
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from pydantic import BaseModel, ValidationError

from app.agents.tools import execute_tool, schemas_for
from app.core.openai_client import get_client, model_id

Emit = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class AgentContext:
    msme: dict[str, Any]
    transactions: list[dict[str, Any]]
    invoices: list[dict[str, Any]]
    metrics: dict[str, Any]
    prior_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    what_if: dict[str, Any] = field(default_factory=dict)
    offline: bool = False


@dataclass
class AgentDef:
    key: str
    name: str
    layer: int
    system_prompt: str
    build_user: Callable[[AgentContext], str]
    tools: list[str]
    output_schema: type[BaseModel]
    build_fallback: Callable[[AgentContext], dict[str, Any]]
    max_iterations: int = 3
    timeout: float = 25.0
    depends_on: list[str] = field(default_factory=list)


def _enrich_metrics(ctx: AgentContext) -> dict[str, Any]:
    """Attach a couple of refs tools need (sector) without leaking raw data."""
    m = dict(ctx.metrics)
    m["_sector"] = ctx.msme.get("sector", "")
    m["_vintage"] = ctx.msme.get("vintage_years", 0)
    return m


async def _emit(emit: Emit, **kw: Any) -> None:
    await emit({"type": "agent_event", **kw})


async def run_agent(agent: AgentDef, ctx: AgentContext, emit: Emit) -> dict[str, Any]:
    """Run one agent (live tool-calling loop or offline fallback). Returns output dict."""
    started = time.time()
    await _emit(emit, agent=agent.key, name=agent.name, stage="start", layer=agent.layer,
                detail=f"{agent.name} starting")
    m = _enrich_metrics(ctx)

    if ctx.offline or get_client() is None:
        out = await _run_offline(agent, ctx, m, emit)
        await _emit(emit, agent=agent.key, name=agent.name, stage="done", layer=agent.layer,
                    detail=f"{agent.name} complete (offline/deterministic)",
                    duration_ms=int((time.time() - started) * 1000), status="done", offline=True)
        return out

    try:
        out = await asyncio.wait_for(_run_live(agent, ctx, m, emit), timeout=agent.timeout)
        await _emit(emit, agent=agent.key, name=agent.name, stage="done", layer=agent.layer,
                    detail=f"{agent.name} complete", duration_ms=int((time.time() - started) * 1000),
                    status="done", offline=False)
        return out
    except asyncio.TimeoutError:
        await _emit(emit, agent=agent.key, name=agent.name, stage="failed", layer=agent.layer,
                    detail=f"{agent.name} timed out — using deterministic fallback", status="fallback")
        return await _run_offline(agent, ctx, m, emit)
    except Exception as e:  # noqa: BLE001
        await _emit(emit, agent=agent.key, name=agent.name, stage="failed", layer=agent.layer,
                    detail=f"{agent.name} error: {e!s:.200} — using fallback", status="fallback")
        return await _run_offline(agent, ctx, m, emit)


async def _run_offline(agent: AgentDef, ctx: AgentContext, m: dict, emit: Emit) -> dict[str, Any]:
    """Deterministic fallback. Emits tool-consult events to keep the trace agentic."""
    for tname in agent.tools[:3]:
        try:
            res = execute_tool(tname, {}, m)
            await _emit(emit, agent=agent.key, name=agent.name, stage="tool_call",
                        tool=tname, result=res, offline=True)
        except Exception:
            pass
    out = agent.build_fallback(ctx)
    await _emit(emit, agent=agent.key, name=agent.name, stage="reasoning",
                detail=(out.get("summary", "")[:300]), offline=True)
    return out


async def _run_live(agent: AgentDef, ctx: AgentContext, m: dict, emit: Emit) -> dict[str, Any]:
    client = get_client()
    assert client is not None
    tool_schemas = schemas_for(agent.tools)
    messages = [
        {"role": "system", "content": agent.system_prompt},
        {"role": "user", "content": agent.build_user(ctx)},
    ]
    last_content = ""
    forced_final = False
    for it in range(agent.max_iterations):
        resp = await client.chat.completions.create(
            model=model_id(), messages=messages, tools=tool_schemas, tool_choice="auto",
            temperature=0.2,
        )
        msg = resp.choices[0].message
        if msg.tool_calls and not forced_final:
            messages.append({"role": "assistant", "content": msg.content or "",
                             "tool_calls": [tc.model_dump() for tc in msg.tool_calls]})
            for tc in msg.tool_calls:
                args = {}
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except Exception:
                    args = {}
                res = execute_tool(tc.function.name, args, m)
                await _emit(emit, agent=agent.key, name=agent.name, stage="tool_call",
                            tool=tc.function.name, arguments=args, result=res)
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": json.dumps(res, default=str)})
            continue
        last_content = msg.content or ""
        await _emit(emit, agent=agent.key, name=agent.name, stage="reasoning", detail=last_content[:400])
        break
    else:
        # No final answer within iterations — force one without tools.
        forced_final = True
        resp = await client.chat.completions.create(model=model_id(), messages=messages, temperature=0.2)
        last_content = resp.choices[0].message.content or ""

    return await _parse_output(agent, last_content, ctx, emit)


async def _parse_output(agent: AgentDef, content: str, ctx: AgentContext,
                        emit: Emit) -> dict[str, Any]:
    raw = _extract_json(content)
    try:
        obj = agent.output_schema.model_validate(raw)
        return obj.model_dump()
    except ValidationError as ve:
        # one async repair attempt
        if get_client() is not None:
            repaired = await _repair(agent, content, ve)
            if repaired:
                try:
                    obj = agent.output_schema.model_validate(repaired)
                    return obj.model_dump()
                except Exception:
                    pass
        await _emit(emit, agent=agent.key, name=agent.name, stage="fallback",
                    detail="schema validation failed — using deterministic fallback")
        return agent.build_fallback(ctx)


def _extract_json(content: str) -> dict[str, Any]:
    s = (content or "").strip()
    if s.startswith("```"):
        parts = s.split("```")
        s = parts[1] if len(parts) > 1 else s
        if s.startswith("json"):
            s = s[4:]
    i, j = s.find("{"), s.rfind("}")
    if i >= 0 and j > i:
        s = s[i:j + 1]
    try:
        return json.loads(s)
    except Exception:
        return {}


async def _repair(agent: AgentDef, content: str, ve: ValidationError) -> dict[str, Any]:
    client = get_client()
    if not client:
        return {}
    schema_hint = json.dumps(agent.output_schema.model_json_schema(), default=str)[:1500]
    prompt = (f"Your previous output failed Pydantic validation: {ve.errors()[:5]}. "
              f"Return ONLY valid JSON matching this schema: {schema_hint}. "
              f"Previous output to fix: {content[:1500]}")
    try:
        resp = await client.chat.completions.create(
            model=model_id(), messages=[{"role": "system", "content": "You output ONLY valid JSON."},
                                        {"role": "user", "content": prompt}], temperature=0.0)
        return _extract_json(resp.choices[0].message.content or "")
    except Exception:
        return {}