"use client";
import { useState } from "react";
import { whatIf, type Metrics } from "@/lib/api";

export default function WhatIfSlider({ msmeId, onMetrics }: { msmeId: string; onMetrics: (m: Metrics) => void }) {
  const [delta, setDelta] = useState(0);
  const [busy, setBusy] = useState(false);

  async function apply(d: number) {
    setDelta(d);
    setBusy(true);
    try {
      const { metrics } = await whatIf(msmeId, d);
      onMetrics(metrics);
    } finally { setBusy(false); }
  }

  const pct = Math.round(delta * 100);
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm font-semibold text-idbi-blue">What-if: revenue shock</div>
        <div className={`text-sm font-mono font-bold ${pct < 0 ? "text-red-600" : pct > 0 ? "text-green-600" : "text-slate-700"}`}>
          {pct > 0 ? "+" : ""}{pct}%
        </div>
      </div>
      <input
        type="range" min={-50} max={50} step={5} value={delta * 100}
        onChange={(e) => setDelta(Number(e.target.value) / 100)}
        onMouseUp={(e) => apply(Number((e.target as HTMLInputElement).value) / 100)}
        onTouchEnd={(e) => apply(Number((e.target as HTMLInputElement).value) / 100)}
        className="w-full accent-idbi-orange"
      />
      <div className="flex justify-between text-[10px] text-slate-400 mt-1">
        <span>−50%</span><span>0%</span><span>+50%</span>
      </div>
      <div className="flex gap-2 mt-2">
        <button onClick={() => apply(-0.2)} className="text-xs border border-slate-300 rounded px-2 py-1 hover:bg-slate-50">−20%</button>
        <button onClick={() => apply(0)} className="text-xs border border-slate-300 rounded px-2 py-1 hover:bg-slate-50">Reset</button>
        <button onClick={() => apply(0.2)} className="text-xs border border-slate-300 rounded px-2 py-1 hover:bg-slate-50">+20%</button>
        {busy && <span className="text-[10px] text-slate-400 self-center">recomputing…</span>}
      </div>
      <div className="text-[10px] text-slate-400 mt-2">Deterministic re-forecast (no LLM) — updates the chart &amp; stress probabilities live.</div>
    </div>
  );
}