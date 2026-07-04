import type { Metrics } from "@/lib/api";

function band(v: number): { c: string; label: string } {
  if (v >= 70) return { c: "#16a34a", label: "Strong" };
  if (v >= 50) return { c: "#F7931E", label: "Adequate" };
  if (v >= 35) return { c: "#ea580c", label: "Marginal" };
  return { c: "#dc2626", label: "Weak" };
}

const SUB_LABELS: Record<string, string> = {
  vintage: "Vintage", sector_risk: "Sector", cash_buffer: "Cash buffer",
  emi_burden: "EMI burden", gst_consistency: "GST consistency", dscr_adj: "DSCR (adj)",
};

export default function ScoreTiles({ m }: { m: Metrics }) {
  const h = band(m.health_score);
  const r = band(m.loan_readiness);
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <Gauge label="Health score" value={`${m.health_score}`} suffix="/100" color={h.c} sub={h.label} />
      <Gauge label="Loan readiness" value={`${m.loan_readiness}`} suffix="/100" color={r.c} sub={r.label} />
      <Gauge label="Cash buffer" value={`${Math.round(m.cash_buffer_days)}`} suffix=" days" color={m.cash_buffer_days >= 30 ? "#16a34a" : m.cash_buffer_days >= 14 ? "#F7931E" : "#dc2626"} sub={m.cash_buffer_days < 21 ? "Low" : "Healthy"} />
      <Gauge label="DSCR" value={`${m.dscr}`} suffix="" color={m.avg_monthly_emi === 0 ? "#64748b" : m.dscr >= 1.3 ? "#16a34a" : m.dscr >= 1.0 ? "#F7931E" : "#dc2626"} sub={m.avg_monthly_emi === 0 ? "No debt" : m.dscr >= 1.3 ? "Strong" : m.dscr >= 1.0 ? "Adequate" : "Stressed"} />

      <div className="col-span-2 lg:col-span-4 bg-white rounded-xl border border-slate-200 p-4">
        <div className="text-xs font-semibold text-slate-500 mb-2">SUB-SCORE BREAKDOWN (0–1 each)</div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-2">
          {Object.entries(m.sub_scores).map(([k, v]) => (
            <div key={k}>
              <div className="flex justify-between text-xs"><span className="text-slate-600">{SUB_LABELS[k] || k}</span><span className="font-mono text-slate-800">{v.toFixed(2)}</span></div>
              <div className="h-1.5 bg-slate-100 rounded mt-1 overflow-hidden">
                <div className="h-full rounded" style={{ width: `${Math.round(v * 100)}%`, background: v >= 0.66 ? "#16a34a" : v >= 0.4 ? "#F7931E" : "#dc2626" }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Gauge({ label, value, suffix, color, sub }: { label: string; value: string; suffix: string; color: string; sub: string }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="flex items-baseline gap-1 mt-1">
        <span className="text-3xl font-bold" style={{ color }}>{value}</span>
        <span className="text-sm text-slate-400">{suffix}</span>
      </div>
      <div className="text-[11px] mt-1 font-medium" style={{ color }}>{sub}</div>
    </div>
  );
}