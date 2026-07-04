"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { sseUrl, getRunStatus, getRunReport, getMsme, type Metrics, type Report, type MsmeSummary } from "@/lib/api";
import ScoreTiles from "@/components/ScoreTiles";
import CashflowChart from "@/components/CashflowChart";
import AgentTrace from "@/components/AgentTrace";
import WhatIfSlider from "@/components/WhatIfSlider";
import ReportView from "@/components/ReportView";

export default function RunPage({ params }: { params: { id: string } }) {
  const runId = params.id;
  const [events, setEvents] = useState<any[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [whatIfMetrics, setWhatIfMetrics] = useState<Metrics | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [msme, setMsme] = useState<MsmeSummary | null>(null);
  const [live, setLive] = useState(true);
  const [done, setDone] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    let msmeId: string | null = null;

    async function init() {
      const st = await getRunStatus(runId);
      if (cancelled) return;
      msmeId = st.msme_id;
      setLive(st.live === true);
      if (msmeId) {
        getMsme(msmeId).then((d) => !cancelled && setMsme(d.msme)).catch(() => {});
      }
      if (st.status === "done" && !st.live) {
        // replay: load report immediately
        const r = await getRunReport(runId);
        if (cancelled) return;
        if (r.metrics) setMetrics(r.metrics);
        if (r.report) setReport(r.report);
        setDone(true);
      }
      openStream();
    }

    function openStream() {
      const es = new EventSource(sseUrl(runId));
      esRef.current = es;
      es.onmessage = (msg) => {
        let ev: any;
        try { ev = JSON.parse(msg.data); } catch { return; }
        if (ev.type === "__closed__") return;
        setEvents((prev) => [...prev, ev]);
        if (ev.type === "metrics" && ev.metrics) setMetrics(ev.metrics);
        if (ev.type === "pipeline_done" || ev.type === "pipeline_end") {
          setDone(true);
          getRunReport(runId).then((r) => {
            if (cancelled) return;
            if (r.metrics) setMetrics(r.metrics);
            if (r.report) setReport(r.report);
          }).catch(() => {});
          es.close();
        }
      };
      es.onerror = () => {
        // fallback: poll status once
        getRunStatus(runId).then((s) => {
          if (cancelled) return;
          if (s.status === "done" || s.status === "failed") {
            setDone(true);
            getRunReport(runId).then((r) => { if (cancelled) return; if (r.metrics) setMetrics(r.metrics); if (r.report) setReport(r.report); }).catch(() => {});
            es.close();
          }
        }).catch(() => {});
      };
    }

    init();
    return () => { cancelled = true; esRef.current?.close(); };
  }, [runId]);

  const chartMetrics = whatIfMetrics || metrics;
  const offlineBadge = (
    <span className="text-[10px] font-semibold bg-slate-100 text-slate-600 px-2 py-1 rounded-full">
      {metrics ? "deterministic + templated" : ""}
    </span>
  );

  return (
    <div>
      <div className="no-print flex items-center gap-3 mb-4">
        <Link href="/msmes" className="text-sm text-idbi-blue hover:underline">← Back to customers</Link>
        <div className="ml-auto flex items-center gap-2">
          {metrics?.near_miss_inclusion && (
            <span className="text-[10px] font-bold bg-idbi-orange/15 text-idbi-orange px-2 py-1 rounded-full">★ Near-miss inclusion case</span>
          )}
          <span className={`text-[10px] font-semibold px-2 py-1 rounded-full ${done ? "bg-green-100 text-green-700" : "bg-blue-100 text-blue-700"}`}>
            {done ? "✓ complete" : "● running"}
          </span>
        </div>
      </div>

      <div className="mb-4">
        <h1 className="text-2xl font-bold text-idbi-blue">{msme?.name || "Analysis"}</h1>
        <div className="text-sm text-slate-500">
          {msme ? `${msme.sub_sector} · ${msme.city}, ${msme.state} · ${msme.udyam_number}` : runId}
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          {chartMetrics ? (
            <>
              <ScoreTiles m={chartMetrics} />
              {msme && <WhatIfSlider msmeId={msme.id} onMetrics={setWhatIfMetrics} />}
              <CashflowChart m={chartMetrics} />
            </>
          ) : (
            <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-slate-400 text-sm">
              Computing deterministic metrics…
            </div>
          )}
        </div>
        <div className="space-y-4">
          <AgentTrace events={events} live={live && !done} />
        </div>
      </div>

      <div className="mt-4">
        {report && metrics ? (
          <ReportView report={report} metrics={whatIfMetrics || metrics} />
        ) : done ? (
          <div className="bg-white rounded-xl border border-slate-200 p-6 text-center text-slate-400 text-sm">Loading report…</div>
        ) : (
          <div className="bg-white rounded-xl border border-slate-200 p-6 text-center text-slate-400 text-sm">
            The Report Agent will assemble the bilingual explainable report once the pipeline completes.
          </div>
        )}
      </div>
    </div>
  );
}