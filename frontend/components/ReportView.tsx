"use client";
import { useState } from "react";
import type { Report, Metrics } from "@/lib/api";

export default function ReportView({ report, metrics }: { report: Report; metrics: Metrics }) {
  const [lang, setLang] = useState<"en" | "hi">("en");
  const [view, setView] = useState<"owner" | "rm">("owner");

  if (!report) return null;
  const sev = (s: string) => s === "high" ? "bg-red-100 text-red-700" : s === "medium" ? "bg-orange-100 text-orange-700" : "bg-slate-100 text-slate-600";

  return (
    <div id="print-report" className="bg-white rounded-xl border border-slate-200 p-5">
      <div className="no-print flex items-center gap-2 mb-4">
        <div className="inline-flex rounded-lg border border-slate-200 overflow-hidden text-xs">
          <button onClick={() => setView("owner")} className={`px-3 py-1.5 ${view === "owner" ? "bg-idbi-blue text-white" : "bg-white text-slate-600"}`}>Owner view</button>
          <button onClick={() => setView("rm")} className={`px-3 py-1.5 ${view === "rm" ? "bg-idbi-blue text-white" : "bg-white text-slate-600"}`}>RM / Banker view</button>
        </div>
        {view === "owner" && (
          <div className="inline-flex rounded-lg border border-slate-200 overflow-hidden text-xs ml-auto">
            <button onClick={() => setLang("en")} className={`px-3 py-1.5 ${lang === "en" ? "bg-idbi-orange text-white" : "bg-white text-slate-600"}`}>English</button>
            <button onClick={() => setLang("hi")} className={`px-3 py-1.5 ${lang === "hi" ? "bg-idbi-orange text-white" : "bg-white text-slate-600"}`}>हिंदी</button>
          </div>
        )}
        <button onClick={() => window.print()} className="no-print ml-2 text-xs border border-slate-300 rounded px-3 py-1.5 hover:bg-slate-50">🖨 Print / PDF</button>
      </div>

      <div className="print:block">
        <div className="text-lg font-bold text-idbi-blue">{report.title}</div>
        <div className="text-sm text-slate-600 mb-3">{report.one_line}</div>

        {view === "owner" ? (
          <div>
            <div className="bg-idbi-light rounded-lg p-4 text-slate-800 leading-relaxed">
              {report.owner[lang]}
            </div>
            <div className="mt-4">
              <div className="text-xs font-semibold text-slate-500 mb-1.5">RECOMMENDED NEXT STEPS</div>
              <ul className="space-y-1.5">
                {report.recommendations.map((r, i) => (
                  <li key={i} className="text-sm text-slate-700 flex gap-2"><span className="text-idbi-orange font-bold">{i + 1}.</span>{r}</li>
                ))}
              </ul>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <Section title="Banker summary">{report.rm.summary}</Section>
            <div className="grid md:grid-cols-2 gap-4">
              <Section title="Next-best-actions" list={report.rm.next_best_actions} />
              <Section title="Cross-sell opportunities" list={report.rm.cross_sell} />
            </div>
            <Section title="Risk for bank">{report.rm.risk_for_bank}</Section>
            <div>
              <div className="text-xs font-semibold text-slate-500 mb-1.5">EARLY-WARNING SIGNALS</div>
              <div className="space-y-1.5">
                {(metrics.early_warning_signals || []).map((s, i) => (
                  <div key={i} className="text-sm flex items-start gap-2">
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${sev(s.severity)}`}>{s.severity}</span>
                    <span className="text-slate-800 font-medium">{s.signal}</span>
                    <span className="text-slate-500">— {s.detail}</span>
                  </div>
                ))}
              </div>
            </div>
            <Section title="Regulatory & compliance notes" list={report.rm.regulatory_notes} />
            {metrics.near_miss_inclusion && (
              <div className="bg-idbi-orange/10 border border-idbi-orange/30 rounded-lg p-3 text-sm text-idbi-deep">
                <b>Near-miss inclusion case:</b> This MSME fails the naive bureau gate (DSCR/cash-buffer) but is
                OD-CC-eligible on cash-flow XAI — sanction with documented rationale.
              </div>
            )}
          </div>
        )}

        <div className="mt-5 border-t border-slate-200 pt-3">
          <div className="text-xs font-semibold text-slate-500 mb-1.5">PROVENANCE (every claim traces to a deterministic metric)</div>
          <div className="flex flex-wrap gap-1.5">
            {report.provenance.map((p, i) => (
              <span key={i} className="text-[10px] bg-slate-100 text-slate-600 px-2 py-1 rounded border border-slate-200" title={p.source_metric}>
                <b className="text-idbi-blue">{p.source_agent}</b>: {p.text}
              </span>
            ))}
          </div>
        </div>
        <div className="text-[10px] text-slate-400 mt-3">
          UdyamMitra AI · Loan-readiness indicator is a prototype derived from cash-flow &amp; GST patterns — NOT a CIBIL/bureau credit score.
        </div>
      </div>
    </div>
  );
}

function Section({ title, children, list }: { title: string; children?: React.ReactNode; list?: string[] }) {
  return (
    <div>
      <div className="text-xs font-semibold text-slate-500 mb-1.5">{title}</div>
      {list ? <ul className="space-y-1">{list.map((x, i) => <li key={i} className="text-sm text-slate-700 flex gap-2"><span className="text-idbi-orange">•</span>{x}</li>)}</ul>
        : <div className="text-sm text-slate-700 leading-relaxed">{children}</div>}
    </div>
  );
}