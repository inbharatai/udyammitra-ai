export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export interface MsmeSummary {
  id: string;
  name: string;
  sector: string;
  sub_sector: string;
  udyam_number: string;
  gstin: string;
  city: string;
  state: string;
  vintage_years: number;
  entity_type: string;
  annual_turnover_lakh: number;
  is_near_miss: boolean;
  profile: Record<string, any>;
}

export interface Metrics {
  msme_id: string;
  health_score: number;
  loan_readiness: number;
  dscr: number;
  cash_buffer_days: number;
  emi_burden_ratio: number;
  seasonality_index: number;
  gst_consistency: number;
  gst_delayed: number;
  gst_missing: number;
  current_balance: number;
  current_ratio: number;
  stress_probabilities: { "30d": number; "60d": number; "90d": number };
  sub_scores: Record<string, number>;
  monthly_series: { month: string; revenue: number; opex: number; emi: number; net: number }[];
  balance_path: { month: string; balance: number }[];
  projection: { month: string; revenue: number; opex: number; emi: number; net: number; balance: number }[];
  projection_min_balance: number;
  working_capital_gap_lakh: number;
  od_cc_limit_lakh: number;
  invoice_discounting_eligible: boolean;
  early_warning_signals: { signal: string; severity: string; detail: string; source_metric: string; action: string }[];
  near_miss_inclusion: boolean;
  naive_bureau_eligible: boolean;
  avg_monthly_revenue: number;
  avg_monthly_opex: number;
  avg_monthly_emi: number;
  invoice_count: number;
  data_months: number;
}

export interface Report {
  title: string;
  one_line: string;
  owner: { en: string; hi: string };
  rm: {
    summary: string;
    next_best_actions: string[];
    cross_sell: string[];
    risk_for_bank: string;
    regulatory_notes: string[];
    early_warning_signals: any[];
    sub_scores: Record<string, number>;
  };
  health_score: number;
  loan_readiness: number;
  recommendations: string[];
  provenance: { text: string; source_agent: string; source_metric: string }[];
}

export async function listMsmes(): Promise<MsmeSummary[]> {
  const r = await fetch(`${API_BASE}/api/msmes`);
  const d = await r.json();
  return d.msmes;
}

export async function getMsme(id: string) {
  const r = await fetch(`${API_BASE}/api/msmes/${id}`);
  return r.json();
}

export async function createRun(msmeId: string): Promise<{ run_id: string; offline: boolean }> {
  const r = await fetch(`${API_BASE}/api/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ msme_id: msmeId }),
  });
  return r.json();
}

export async function getRunStatus(runId: string) {
  const r = await fetch(`${API_BASE}/api/runs/${runId}/status`);
  return r.json();
}

export async function getRunReport(runId: string): Promise<{ status: string; offline: boolean; metrics: Metrics; report: Report; msme_id: string }> {
  const r = await fetch(`${API_BASE}/api/runs/${runId}/report`);
  return r.json();
}

export async function whatIf(msmeId: string, revenueDelta: number): Promise<{ metrics: Metrics }> {
  const r = await fetch(`${API_BASE}/api/msmes/${msmeId}/what-if`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ revenue_delta: revenueDelta }),
  });
  return r.json();
}

export function sseUrl(runId: string): string {
  return `${API_BASE}/api/runs/${runId}/events`;
}