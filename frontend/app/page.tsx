import Link from "next/link";
import Logo from "@/components/Logo";

const features = [
  ["MSME financial health score", "Weighted sub-scores: vintage, sector, cash buffer, EMI burden, GST consistency, DSCR."],
  ["Cash-flow forecast", "30/60/90-day stress probability from a seasonality-adjusted projected balance path."],
  ["Loan readiness indicator", "Transparent, explainable — not a black box, not a bureau score."],
  ["Early-warning signals", "Actionable: low cash buffer, EMI burden, GST gaps, negative-cash months."],
  ["Working-capital recommendation", "OD/CC limit, invoice discounting, term loan — with rationale and ₹ lakh figures."],
  ["Scheme & product matching", "CGTMSE, MUDRA, PM Vishwakarma, PMEGP, RAMP + IDBI MSME products."],
  ["RM copilot", "Banker brief: next-best-actions, cross-sell, talking points, risk-for-bank."],
  ["Bilingual explainable report", "Owner view in Hindi + English; banker view with full provenance footnotes."],
];

const agents = [
  "Profile", "Transaction", "Forecast", "Credit Risk", "Early Warning",
  "Loan Suitability", "Scheme Match", "Compliance & XAI", "RM Copilot", "Report",
];

export default function Home() {
  return (
    <div>
      <section className="grid md:grid-cols-2 gap-8 items-center py-8">
        <div>
          <div className="inline-flex items-center gap-2 bg-idbi-light text-idbi-blue text-xs font-semibold px-3 py-1 rounded-full mb-4">
            IDBI MSME Track · Prototype
          </div>
          <h1 className="text-4xl md:text-5xl font-bold text-idbi-blue leading-tight tracking-tight">
            AI credit &amp; cash-flow <br /> intelligence for <span className="text-idbi-orange">MSMEs</span>.
          </h1>
          <p className="mt-4 text-slate-600 text-lg max-w-xl">
            UdyamMitra AI analyses an MSME&apos;s banking, GST and cash-flow data through a
            10-agent explainable pipeline — producing a health score, stress forecast,
            loan-readiness indicator, working-capital recommendation and a bilingual report.
          </p>
          <div className="mt-6 flex gap-3">
            <Link href="/msmes" className="bg-idbi-blue text-white font-semibold px-5 py-3 rounded-lg hover:bg-idbi-deep transition">
              Analyse an MSME →
            </Link>
            <Link href="/msmes" className="border border-slate-300 text-slate-700 font-semibold px-5 py-3 rounded-lg hover:bg-slate-50 transition">
              View demo customers
            </Link>
          </div>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <Logo size={44} />
            <div className="font-bold text-idbi-blue text-xl">10-Agent Pipeline</div>
          </div>
          <div className="flex flex-wrap gap-2">
            {agents.map((a, i) => (
              <span key={a} className="text-xs font-medium bg-slate-100 text-slate-700 px-2.5 py-1.5 rounded-md border border-slate-200">
                <span className="text-idbi-orange mr-1">{i + 1}</span>{a}
              </span>
            ))}
          </div>
          <div className="mt-4 text-xs text-slate-500">
            Parallel multi-agent execution · live reasoning trace · tool-calling · structured outputs · provenance-tagged.
          </div>
        </div>
      </section>

      <section className="py-6">
        <h2 className="text-2xl font-bold text-idbi-blue mb-4">What it delivers</h2>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
          {features.map(([t, d]) => (
            <div key={t} className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
              <div className="font-semibold text-idbi-blue text-sm">{t}</div>
              <div className="text-xs text-slate-600 mt-1.5 leading-relaxed">{d}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="py-6">
        <div className="bg-idbi-blue text-white rounded-2xl p-6 flex flex-col md:flex-row items-center gap-4 justify-between">
          <div>
            <div className="font-bold text-lg">Credit inclusion, risk reduction, MSME growth.</div>
            <div className="text-sm text-blue-100">See the near-miss inclusion case: flagged OD-CC-eligible where naive logic declines.</div>
          </div>
          <Link href="/msmes" className="bg-idbi-orange text-white font-semibold px-5 py-3 rounded-lg hover:bg-idbi-amber transition whitespace-nowrap">
            Try the demo →
          </Link>
        </div>
      </section>
    </div>
  );
}