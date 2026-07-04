"use client";
import {
  ResponsiveContainer, ComposedChart, Line, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, ReferenceLine,
} from "recharts";
import type { Metrics } from "@/lib/api";

export default function CashflowChart({ m }: { m: Metrics }) {
  // combine historical balance + projection into one series with a split at 'now'
  const hist = m.balance_path.map((b) => ({ month: b.month, balance: b.balance, type: "Actual" }));
  const proj = m.projection.map((p) => ({ month: p.month, balance: p.balance, revenue: p.revenue, type: "Forecast" }));
  const data = [...hist, ...proj];
  const stress = m.stress_probabilities;

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm font-semibold text-idbi-blue">Cash balance trajectory (₹)</div>
        <div className="flex gap-3 text-[11px]">
          <StressPill label="30d" v={stress["30d"]} />
          <StressPill label="60d" v={stress["60d"]} />
          <StressPill label="90d" v={stress["90d"]} />
        </div>
      </div>
      <div style={{ width: "100%", height: 260 }}>
        <ResponsiveContainer>
          <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" />
            <XAxis dataKey="month" tick={{ fontSize: 10 }} interval={Math.max(1, Math.floor(data.length / 8))} />
            <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => (Math.abs(v) >= 1e5 ? `${(v / 1e5).toFixed(0)}L` : `${(v / 1000).toFixed(0)}k`)} width={48} />
            <Tooltip
              contentStyle={{ fontSize: 11, borderRadius: 8, border: "1px solid #e2e8f0" }}
              formatter={(v: any) => new Intl.NumberFormat("en-IN").format(Math.round(v))}
              labelStyle={{ fontWeight: 600 }}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <ReferenceLine y={0} stroke="#dc2626" strokeDasharray="4 4" strokeOpacity={0.5} label={{ value: "zero", fontSize: 9, fill: "#dc2626", position: "insideTopRight" }} />
            <ReferenceLine x={hist.length - 1} stroke="#F7931E" strokeDasharray="4 4" label={{ value: "now", fontSize: 9, fill: "#F7931E", position: "top" }} />
            <Area type="monotone" dataKey="balance" name="Balance" stroke="#003B73" strokeWidth={2.5} fill="#003B73" fillOpacity={0.08} connectNulls />
            <Line type="monotone" dataKey="revenue" name="Forecast revenue" stroke="#F7931E" strokeWidth={1.8} strokeDasharray="5 4" dot={false} connectNulls />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="text-[11px] text-slate-500 mt-1">
        Solid line = actual cash balance · dashed orange = forecast revenue · stress pills = projected cash-flow stress probability.
      </div>
    </div>
  );
}

function StressPill({ label, v }: { label: string; v: number }) {
  const c = v >= 0.6 ? "#dc2626" : v >= 0.3 ? "#F7931E" : "#16a34a";
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full border" style={{ color: c, borderColor: c + "40", background: c + "10" }}>
      <span className="font-semibold">{Math.round(v * 100)}%</span><span className="text-slate-500">{label} stress</span>
    </span>
  );
}