"use client";
import { useMemo } from "react";

interface TraceProps {
  events: any[];
  live: boolean;
}

const LAYER_COLOR = ["#003B73", "#0A6EBD", "#0A6EBD", "#F7931E", "#64748b", "#64748b", "#16a34a"];

export default function AgentTrace({ events, live }: TraceProps) {
  const { agents, pipelineElapsed, done } = useMemo(() => {
    const map = new Map<string, any>();
    let elapsed: string | null = null;
    let isDone = false;
    for (const ev of events) {
      if (ev.type === "pipeline_done") { elapsed = ev.elapsed_s != null ? `${ev.elapsed_s}s` : null; isDone = true; }
      if (ev.type === "pipeline_end") { isDone = true; }
      if (ev.type !== "agent_event") continue;
      const k = ev.agent;
      if (!map.has(k)) map.set(k, { key: k, name: ev.name, layer: ev.layer, stage: ev.stage, tools: [], detail: "", status: "running", offline: ev.offline });
      const a = map.get(k);
      if (ev.stage === "tool_call") {
        a.tools.push({ tool: ev.tool, result: ev.result, offline: ev.offline });
      } else {
        a.stage = ev.stage;
        if (ev.detail) a.detail = ev.detail;
        if (ev.stage === "done") a.status = ev.status || "done";
        if (ev.stage === "failed") a.status = "fallback";
      }
    }
    const agents = Array.from(map.values()).sort((a, b) => a.layer - b.layer || a.key.localeCompare(b.key));
    return { agents, pipelineElapsed: elapsed, done: isDone };
  }, [events]);

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-semibold text-idbi-blue flex items-center gap-2">
          Agent reasoning trace
          {live && !done && <span className="inline-block w-2 h-2 rounded-full bg-red-500 live-dot" />}
        </div>
        <div className="text-[11px] text-slate-500">{done ? `Pipeline complete${pipelineElapsed ? ` · ${pipelineElapsed}` : ""}` : "running…"}</div>
      </div>
      <div className="space-y-2 max-h-[420px] overflow-y-auto trace-scroll pr-1">
        {agents.length === 0 && <div className="text-xs text-slate-400">Waiting for agents to start…</div>}
        {agents.map((a) => (
          <div key={a.key} className="border border-slate-200 rounded-lg p-2.5">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded text-white" style={{ background: LAYER_COLOR[a.layer] || "#64748b" }}>L{a.layer}</span>
              <span className="text-sm font-medium text-slate-800">{a.name}</span>
              <span className={`ml-auto text-[10px] font-semibold px-2 py-0.5 rounded-full ${statusClass(a.status)}`}>
                {a.status === "running" ? "● running" : a.status === "fallback" ? "⚠ fallback" : a.status === "done" ? (a.offline ? "✓ done (offline)" : "✓ done") : a.status}
              </span>
            </div>
            {a.tools.length > 0 && (
              <div className="mt-1.5 flex flex-wrap gap-1">
                {a.tools.map((t: any, i: number) => (
                  <span key={i} className="text-[10px] font-mono bg-idbi-light text-idbi-blue px-1.5 py-0.5 rounded" title={JSON.stringify(t.result).slice(0, 200)}>
                    🔧 {t.tool}
                  </span>
                ))}
              </div>
            )}
            {a.detail && <div className="text-[11px] text-slate-500 mt-1.5 line-clamp-3">{a.detail}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}

function statusClass(s: string) {
  if (s === "done") return "bg-green-100 text-green-700";
  if (s === "fallback") return "bg-orange-100 text-orange-700";
  if (s === "failed") return "bg-red-100 text-red-700";
  return "bg-blue-100 text-blue-700";
}