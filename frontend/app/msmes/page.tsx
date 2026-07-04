"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { listMsmes, createRun, type MsmeSummary } from "@/lib/api";

export default function MsmesPage() {
  const router = useRouter();
  const [msmes, setMsmes] = useState<MsmeSummary[]>([]);
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { listMsmes().then(setMsmes).catch((e) => setError(String(e))); }, []);

  async function run(m: MsmeSummary) {
    setLoading(m.id);
    try {
      const { run_id } = await createRun(m.id);
      router.push(`/runs/${run_id}`);
    } catch (e) {
      setError(String(e));
      setLoading(null);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-2xl font-bold text-idbi-blue">Demo MSME customers</h1>
          <p className="text-sm text-slate-600">Synthetic, realistic Indian MSMEs with 24 months of banking + GST data. Pick one to run the 10-agent analysis.</p>
        </div>
        {error && <div className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded">{error}</div>}
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {msmes.map((m) => (
          <div key={m.id} className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm flex flex-col">
            <div className="flex items-start justify-between">
              <div>
                <div className="font-bold text-idbi-blue">{m.name}</div>
                <div className="text-xs text-slate-500">{m.sub_sector} · {m.city}, {m.state}</div>
              </div>
              {m.is_near_miss && (
                <span className="text-[10px] font-bold bg-idbi-orange/15 text-idbi-orange px-2 py-1 rounded-full whitespace-nowrap" title="Near-miss inclusion case">
                  ★ Near-miss
                </span>
              )}
            </div>
            <div className="grid grid-cols-2 gap-2 mt-4 text-xs">
              <Stat label="Sector" value={m.sector} />
              <Stat label="Entity" value={m.entity_type} />
              <Stat label="Vintage" value={`${m.vintage_years} yrs`} />
              <Stat label="Turnover" value={`₹${m.annual_turnover_lakh} lakh`} />
            </div>
            <div className="text-[10px] text-slate-400 mt-3 font-mono">{m.udyam_number}</div>
            <button
              onClick={() => run(m)}
              disabled={loading !== null}
              className="mt-4 bg-idbi-blue text-white text-sm font-semibold px-4 py-2.5 rounded-lg hover:bg-idbi-deep transition disabled:opacity-50"
            >
              {loading === m.id ? "Starting pipeline…" : "Run analysis →"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-slate-400">{label}</div>
      <div className="text-slate-800 font-medium">{value}</div>
    </div>
  );
}