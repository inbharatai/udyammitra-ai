"""Definitions for all 10 agents: system prompts, tools, schemas, fallbacks.

The fallback builders are the substance — they turn the deterministic metrics
into banker-quality structured narrative, so the pipeline produces a real,
coherent, explainable report even with zero network (OPENAI_DISABLED / no key).
In live mode the LLM consults the same tools and improves the narrative.
"""
from __future__ import annotations

import json
from typing import Any

from app.agents.base import AgentContext, AgentDef
from app.agents.schemas import (
    Claim, ComplianceXAIOutput, CreditRiskOutput, EarlyWarningOutput,
    ForecastOutput, LoanSuitabilityOutput, ProfileOutput, ReportOutput,
    RMCopilotOutput, SchemeMatchOutput, TransactionOutput,
)
from app.agents.tools import execute_tool, load_schemes


# ---- helpers ----
def _inr(x: float) -> str:
    if abs(x) >= 1e7:
        return f"₹{x/1e7:.2f} Cr"
    if abs(x) >= 1e5:
        return f"₹{x/1e5:.2f} lakh"
    return f"₹{x:,.0f}"


def _ctx_brief(ctx: AgentContext) -> str:
    m = ctx.metrics
    p = ctx.msme.get("profile", {}) or {}
    brief = {
        "msme": ctx.msme.get("name"), "sector": ctx.msme.get("sector"),
        "sub_sector": ctx.msme.get("sub_sector"), "vintage_years": ctx.msme.get("vintage_years"),
        "entity_type": ctx.msme.get("entity_type"), "city": ctx.msme.get("city"),
        "state": ctx.msme.get("state"), "seasonality": p.get("seasonality"),
        "stated_turnover_lakh": m.get("stated_turnover_lakh"),
        "avg_monthly_revenue": m.get("avg_monthly_revenue"),
        "avg_monthly_opex": m.get("avg_monthly_opex"), "avg_monthly_emi": m.get("avg_monthly_emi"),
        "emi_burden_ratio": m.get("emi_burden_ratio"), "seasonality_index": m.get("seasonality_index"),
        "cash_buffer_days": m.get("cash_buffer_days"), "dscr": m.get("dscr"),
        "current_ratio": m.get("current_ratio"), "gst_consistency": m.get("gst_consistency"),
        "gst_delayed": m.get("gst_delayed"), "gst_missing": m.get("gst_missing"),
        "stress_probabilities": m.get("stress_probabilities"),
        "health_score": m.get("health_score"), "loan_readiness": m.get("loan_readiness"),
        "sub_scores": m.get("sub_scores"), "working_capital_gap_lakh": m.get("working_capital_gap_lakh"),
        "od_cc_limit_lakh": m.get("od_cc_limit_lakh"),
        "invoice_discounting_eligible": m.get("invoice_discounting_eligible"),
        "near_miss_inclusion": m.get("near_miss_inclusion"),
        "naive_bureau_eligible": m.get("naive_bureau_eligible"),
        "data_months": m.get("data_months"), "invoice_count": m.get("invoice_count"),
    }
    return json.dumps(brief, ensure_ascii=False, default=str)


def _prior_brief(ctx: AgentContext, keys: list[str]) -> str:
    out = {}
    for k in keys:
        o = ctx.prior_outputs.get(k)
        if o:
            out[k] = o.get("summary", str(o))[:400]
    return json.dumps(out, ensure_ascii=False)


# =========================================================================
# 1. MSME PROFILE
# =========================================================================
PROFILE = AgentDef(
    key="profile", name="MSME Profile Agent", layer=0,
    system_prompt=(
        "You are the MSME Profile Agent for an Indian bank credit-intelligence tool. "
        "Build a concise, accurate profile of the MSME from its Udyam metadata, sector, "
        "vintage and entity type. Note the sector outlook. Be factual and banker-appropriate. "
        "Return JSON matching the given schema."),
    build_user=lambda ctx: f"MSME facts + computed metrics:\n{_ctx_brief(ctx)}",
    tools=["get_health_breakdown"],
    output_schema=ProfileOutput,
    build_fallback=lambda ctx: {
        "summary": (f"{ctx.msme.get('name')} — a {ctx.msme.get('vintage_years')}-year-old "
                    f"{ctx.msme.get('entity_type')} in {ctx.msme.get('sub_sector') or ctx.msme.get('sector')}, "
                    f"based in {ctx.msme.get('city')}, {ctx.msme.get('state')}. "
                    f"Stated annual turnover ≈ ₹{ctx.msme.get('annual_turnover_lakh')} lakh. "
                    f"Udyam: {ctx.msme.get('udyam_number')}; GSTIN: {ctx.msme.get('gstin')}."),
        "sector_outlook": _sector_outlook(ctx.msme.get("sector", "")),
        "vintage_assessment": _vintage_assessment(ctx.msme.get("vintage_years", 0)),
        "key_facts": [
            f"Sector: {ctx.msme.get('sector')} ({ctx.msme.get('sub_sector')})",
            f"Entity: {ctx.msme.get('entity_type')}, vintage {ctx.msme.get('vintage_years')} yrs",
            f"Location: {ctx.msme.get('city')}, {ctx.msme.get('state')}",
            f"Stated turnover: ₹{ctx.msme.get('annual_turnover_lakh')} lakh",
            f"Udyam Reg. No.: {ctx.msme.get('udyam_number')}",
        ],
        "claims": [Claim(text=f"Profile built from Udyam metadata for {ctx.msme.get('name')}",
                         source_agent="profile", source_metric="udyam_metadata").model_dump()],
    },
    depends_on=[],
)


def _sector_outlook(sector: str) -> str:
    out = {
        "Textile": "Moderate outlook — export demand soft, domestic festival demand seasonal; thin margins.",
        "Food Processing": "Favourable — rising packaged-food demand, PLI tailwinds; working-capital intensive.",
        "Manufacturing": "Stable — capex-led growth, China+1 opportunity; cyclical input costs.",
        "Agriculture": "Seasonal & weather-dependent; monsoon and MSP driven; volatile cash flows.",
        "Retail Trading": "Steady but low-margin; FMCG resilient, discretionary cyclical.",
        "Handicrafts": "Export-oriented, seasonal; GI tagging and e-commerce enabling premium realisation.",
        "Services": "Asset-light, high margin, recurring revenue; key-person dependent.",
    }
    return out.get(sector, "Outlook stable; sector-specific risk applies.")


def _vintage_assessment(v: float) -> str:
    if v >= 7: return "Mature — established track record, lower entity risk."
    if v >= 3: return "Established — past startup fragility, growing stability."
    if v >= 1: return "Early-stage — still building track record."
    return "Nascent — high entity risk, limited history."


# =========================================================================
# 2. TRANSACTION ANALYSIS
# =========================================================================
TRANSACTION = AgentDef(
    key="transaction", name="Transaction Analysis Agent", layer=0,
    system_prompt=(
        "You are the Transaction Analysis Agent. Analyse the MSME's banking transactions and "
        "GST invoices to assess revenue stability, expense structure, EMI burden, seasonality and "
        "GST filing consistency. Use the provided tools to pull exact metrics. Cite the metric you used "
        "in each claim's source_metric. Return JSON matching the schema."),
    build_user=lambda ctx: f"MSME + computed metrics:\n{_ctx_brief(ctx)}",
    tools=["get_emi_burden", "get_seasonality", "get_gst_consistency", "get_cash_buffer_days"],
    output_schema=TransactionOutput,
    build_fallback=lambda ctx: _txn_fallback(ctx),
    depends_on=[],
)


def _txn_fallback(ctx: AgentContext) -> dict[str, Any]:
    m = ctx.metrics
    eb = m["emi_burden_ratio"]; si = m["seasonality_index"]; gc = m["gst_consistency"]
    emi_txt = "high" if eb > 0.30 else ("moderate" if eb > 0.15 else "low")
    seas_txt = "highly seasonal" if si > 0.35 else ("moderately seasonal" if si > 0.20 else "stable")
    rev = m["avg_monthly_revenue"]; opex = m["avg_monthly_opex"]
    return {
        "summary": (f"Avg monthly revenue {_inr(rev)} against operating cost {_inr(opex)}; "
                    f"EMI burden {eb*100:.0f}% (={emi_txt}); revenue {seas_txt} "
                    f"(seasonality index {si:.2f}); GST filing consistency {gc*100:.0f}%."),
        "revenue_pattern": (f"Monthly revenue averages {_inr(rev)} over {m['data_months']} months "
                            f"with a coefficient of variation of {si:.2f} — {seas_txt}."),
        "expense_pattern": (f"Operating expenses average {_inr(opex)}/month; EMI {_inr(m['avg_monthly_emi'])}/month."),
        "emi_burden_assessment": (f"EMI consumes {eb*100:.0f}% of revenue — {emi_txt}. "
                                  f"Healthy MSMEs stay under 30%."),
        "seasonality_assessment": f"Seasonality index {si:.2f} indicates {seas_txt} revenue.",
        "gst_consistency_assessment": (f"Of {m['invoice_count']} GST invoices, {m['gst_delayed']} delayed and "
                                       f"{m['gst_missing']} missing — consistency {gc*100:.0f}%."),
        "anomalies": _txn_anomalies(m),
        "claims": [
            Claim(text=f"EMI burden {eb*100:.0f}% of revenue", source_agent="transaction", source_metric="emi_burden_ratio").model_dump(),
            Claim(text=f"Revenue seasonality index {si:.2f}", source_agent="transaction", source_metric="seasonality_index").model_dump(),
            Claim(text=f"GST filing consistency {gc*100:.0f}%", source_agent="transaction", source_metric="gst_consistency").model_dump(),
        ],
    }


def _txn_anomalies(m: dict) -> list[str]:
    a = []
    if m["gst_missing"] > 0:
        a.append(f"{m['gst_missing']} invoices with missing GST filing — reconcile before credit appraisal.")
    if m["emi_burden_ratio"] > 0.40:
        a.append("EMI burden above 40% — debt stress signal.")
    if m["seasonality_index"] > 0.40:
        a.append("Very high seasonality — structure seasonal working-capital limit.")
    return a


# =========================================================================
# 3. CASH-FLOW FORECAST
# =========================================================================
FORECAST = AgentDef(
    key="forecast", name="Cash-flow Forecast Agent", layer=1,
    system_prompt=(
        "You are the Cash-flow Forecast Agent. Project the MSME's cash position over the next "
        "30/60/90 days using the deterministic stress probabilities and projected balance path. "
        "Use tools to pull exact stress probabilities and the cash gap. Give honest confidence bands. "
        "Return JSON matching the schema."),
    build_user=lambda ctx: f"Metrics + prior profile/transaction summaries:\n{_ctx_brief(ctx)}\nPRIOR:\n{_prior_brief(ctx, ['profile','transaction'])}",
    tools=["get_stress_probability", "get_cash_gap", "get_cash_buffer_days"],
    output_schema=ForecastOutput,
    build_fallback=lambda ctx: _forecast_fallback(ctx),
    depends_on=["profile", "transaction"],
)


def _forecast_fallback(ctx: AgentContext) -> dict[str, Any]:
    m = ctx.metrics
    sp = m["stress_probabilities"]
    p30, p60, p90 = sp.get("30d", 0), sp.get("60d", 0), sp.get("90d", 0)
    pmin = m["projection_min_balance"]
    cb = m["current_balance"]
    conf = "medium" if m["data_months"] >= 12 else "low"
    key_risk = ("Projected balance turns negative within 90 days." if pmin < 0
                else f"Minimum projected balance {_inr(pmin)} — adequate but thin." if cb < m["avg_monthly_opex"] * 2
                else "No imminent cash-flow shortfall projected.")
    return {
        "summary": (f"Over 30/60/90 days, projected cash-flow stress probability is "
                    f"{p30*100:.0f}% / {p60*100:.0f}% / {p90*100:.0f}% respectively. "
                    f"Current balance {_inr(cb)}; 90-day projected minimum {_inr(pmin)}."),
        "stress_30d": f"{p30*100:.0f}% probability of cash stress within 30 days.",
        "stress_60d": f"{p60*100:.0f}% probability within 60 days.",
        "stress_90d": f"{p90*100:.0f}% probability within 90 days.",
        "confidence": f"{conf} — based on {m['data_months']} months of deterministic cash-flow modelling.",
        "key_risk": key_risk,
        "claims": [
            Claim(text=f"90-day stress probability {p90*100:.0f}%", source_agent="forecast", source_metric="stress_90d").model_dump(),
            Claim(text=f"Projected minimum balance {_inr(pmin)}", source_agent="forecast", source_metric="projection_min_balance").model_dump(),
        ],
    }


# =========================================================================
# 4. CREDIT RISK
# =========================================================================
CREDIT_RISK = AgentDef(
    key="credit_risk", name="Credit Risk Agent", layer=2,
    system_prompt=(
        "You are the Credit Risk Agent. Produce a loan-readiness indicator (NOT a bureau/CIBIL score) "
        "from the health sub-scores, DSCR, EMI burden and cash buffer. Always list the sub-scores that "
        "compose it — never present an opaque single number. Be honest about weaknesses. "
        "Return JSON matching the schema."),
    build_user=lambda ctx: f"Metrics:\n{_ctx_brief(ctx)}\nPRIOR:\n{_prior_brief(ctx, ['profile','transaction','forecast'])}",
    tools=["get_health_breakdown", "get_dscr", "get_emi_burden", "get_cash_buffer_days"],
    output_schema=CreditRiskOutput,
    build_fallback=lambda ctx: _risk_fallback(ctx),
    depends_on=["profile", "transaction", "forecast"],
)


def _risk_fallback(ctx: AgentContext) -> dict[str, Any]:
    m = ctx.metrics
    lr = m["loan_readiness"]; hs = m["health_score"]; sub = m["sub_scores"]
    band = "Strong" if lr >= 70 else ("Adequate" if lr >= 50 else ("Marginal" if lr >= 35 else "Weak"))
    strengths, weaknesses = [], []
    if sub["gst_consistency"] >= 0.8: strengths.append(f"Strong GST consistency ({sub['gst_consistency']*100:.0f}%).")
    if sub["cash_buffer"] >= 0.6: strengths.append(f"Healthy cash buffer ({m['cash_buffer_days']:.0f} days).")
    if sub["dscr_adj"] >= 0.7: strengths.append(f"Comfortable DSCR ({m['dscr']:.2f}).")
    if sub["vintage"] >= 0.5: strengths.append(f"Established vintage ({ctx.msme.get('vintage_years')} yrs).")
    if sub["emi_burden"] < 0.5: weaknesses.append(f"EMI burden {m['emi_burden_ratio']*100:.0f}% weighs on readiness.")
    if sub["cash_buffer"] < 0.4: weaknesses.append(f"Thin cash buffer ({m['cash_buffer_days']:.0f} days).")
    if sub["dscr_adj"] < 0.4 and m["avg_monthly_emi"] > 0: weaknesses.append(f"Weak DSCR ({m['dscr']:.2f}).")
    if not strengths: strengths.append("Consistent banking turnover visible.")
    if not weaknesses: weaknesses.append("No material weaknesses detected.")
    return {
        "summary": (f"Loan-readiness indicator: {lr}/100 ({band}). Health score {hs}/100. "
                    f"Composed of sub-scores: vintage {sub['vintage']}, sector {sub['sector_risk']}, "
                    f"cash buffer {sub['cash_buffer']}, EMI burden {sub['emi_burden']}, "
                    f"GST consistency {sub['gst_consistency']}, DSCR {sub['dscr_adj']}."),
        "loan_readiness_indicator": f"{lr}/100 — {band}",
        "readiness_value": lr,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "bureau_disclaimer": ("This is a prototype loan-readiness indicator derived from cash-flow and GST "
                               "patterns. It is NOT a CIBIL/bureau credit score and is not a substitute for one."),
        "claims": [
            Claim(text=f"Loan readiness {lr}/100", source_agent="credit_risk", source_metric="loan_readiness").model_dump(),
            Claim(text=f"Health score {hs}/100", source_agent="credit_risk", source_metric="health_score").model_dump(),
        ],
    }


# =========================================================================
# 5. EARLY WARNING
# =========================================================================
EARLY_WARNING = AgentDef(
    key="early_warning", name="Early Warning Agent", layer=2,
    system_prompt=(
        "You are the Early Warning Agent. Produce ACTIONABLE risk signals — each with severity, a concrete "
        "detail and a recommended action — from the deterministic signal set. Avoid vague 'high risk' labels. "
        "If the MSME is a near-miss inclusion case, call it out explicitly. Return JSON matching the schema."),
    build_user=lambda ctx: f"Metrics:\n{_ctx_brief(ctx)}\nPRIOR:\n{_prior_brief(ctx, ['transaction','forecast'])}",
    tools=["get_early_signals", "get_cash_buffer_days", "get_stress_probability"],
    output_schema=EarlyWarningOutput,
    build_fallback=lambda ctx: _ew_fallback(ctx),
    depends_on=["transaction", "forecast"],
)


def _ew_fallback(ctx: AgentContext) -> dict[str, Any]:
    m = ctx.metrics
    sigs = m["early_warning_signals"]
    top = sigs[0]["action"] if sigs else "Maintain monitoring cadence."
    summary = (f"{len(sigs)} signal(s) detected. " +
               ("Near-miss inclusion case: fails naive bureau gate but is OD-CC-eligible on cash-flow XAI. "
                if m["near_miss_inclusion"] else ""))
    return {
        "summary": summary + "Top priority: " + top,
        "signals": sigs,
        "top_action": top,
        "claims": [Claim(text=f"{len(sigs)} early-warning signals", source_agent="early_warning",
                         source_metric="early_warning_signals").model_dump()],
    }


# =========================================================================
# 6. LOAN SUITABILITY
# =========================================================================
LOAN_SUITABILITY = AgentDef(
    key="loan_suitability", name="Loan Suitability Agent", layer=3,
    system_prompt=(
        "You are the Loan Suitability Agent. Recommend the most suitable credit facility for the MSME "
        "(term loan / OD-CC / invoice discounting / advisory) with a suggested limit in ₹ lakh and rationale. "
        "Use tools to pull working-capital gap, cash gap and DSCR. Return JSON matching the schema."),
    build_user=lambda ctx: f"Metrics:\n{_ctx_brief(ctx)}\nPRIOR:\n{_prior_brief(ctx, ['credit_risk','forecast','early_warning'])}",
    tools=["get_working_capital", "get_cash_gap", "get_dscr"],
    output_schema=LoanSuitabilityOutput,
    build_fallback=lambda ctx: _loan_fallback(ctx),
    depends_on=["profile", "transaction", "forecast", "credit_risk"],
)


def _loan_fallback(ctx: AgentContext) -> dict[str, Any]:
    m = ctx.metrics
    gap = m["working_capital_gap_lakh"]; od = m["od_cc_limit_lakh"]
    if gap <= 0 and m["naive_bureau_eligible"]:
        facility = "Term Loan (capex)"; limit = round(m["stated_turnover_lakh"] * 0.15, 2)
        rationale = (f"Strong cash position (no working-capital gap) and healthy DSCR {m['dscr']:.2f}; "
                     f"a term loan for capacity expansion fits.")
    elif m["invoice_discounting_eligible"] and gap > 0:
        facility = "Invoice Discounting + OD/CC"; limit = od
        rationale = (f"Working-capital gap ₹{gap} lakh with {m['invoice_count']} GST invoices and "
                     f"{m['gst_consistency']*100:.0f}% filing consistency — invoice discounting bridges "
                     f"receivables; OD/CC of ₹{od} lakh covers the residual gap.")
    elif gap > 0:
        facility = "OD/CC (Cash Credit)"; limit = od
        rationale = (f"Working-capital gap ₹{gap} lakh over the next 3 months; suggest OD/CC limit "
                     f"₹{od} lakh against drawing power.")
    else:
        facility = "Advisory / scheme-led growth"; limit = 0.0
        rationale = "No immediate credit need; route to govt scheme + advisory for growth capital."
    alts = []
    if facility != "OD/CC (Cash Credit)" and gap > 0: alts.append(f"OD/CC limit ₹{od} lakh")
    if m["invoice_discounting_eligible"] and "Invoice" not in facility: alts.append("Bill/invoice discounting")
    if m["stated_turnover_lakh"] >= 50: alts.append("IDBI MSME Smart Term Loan (capex)")
    return {
        "summary": f"Recommended facility: {facility}" + (f" (suggested limit ₹{limit} lakh)." if limit else "."),
        "recommended_facility": facility,
        "suggested_limit_lakh": limit,
        "rationale": rationale,
        "alternatives": alts or ["CGTMSE-backed facility for collateral-free access"],
        "claims": [Claim(text=f"Working-capital gap ₹{gap} lakh", source_agent="loan_suitability",
                         source_metric="working_capital_gap_lakh").model_dump()],
    }


# =========================================================================
# 7. SCHEME / PRODUCT MATCH
# =========================================================================
SCHEME_MATCH = AgentDef(
    key="scheme_match", name="Scheme/Product Match Agent", layer=3,
    system_prompt=(
        "You are the Scheme/Product Match Agent. Match the MSME to the most relevant 2025-26 government "
        "schemes (CGTMSE, MUDRA tiers, PM Vishwakarma, PMEGP, RAMP) and IDBI MSME products using the "
        "search_schemes tool. Prefer needs (working_capital/term_loan/invoice_discounting/advisory) derived "
        "from prior agents. Return JSON matching the schema."),
    build_user=lambda ctx: f"MSME sector/stage + prior recommendations:\n{_ctx_brief(ctx)}\nPRIOR:\n{_prior_brief(ctx, ['loan_suitability','credit_risk'])}",
    tools=["search_schemes"],
    output_schema=SchemeMatchOutput,
    build_fallback=lambda ctx: _scheme_fallback(ctx),
    depends_on=["profile", "credit_risk"],
)


def _scheme_fallback(ctx: AgentContext) -> dict[str, Any]:
    m = ctx.metrics
    sector = ctx.msme.get("sector", "")
    vintage = ctx.msme.get("vintage_years", 0)
    stage = "startup" if vintage < 3 else ("growth" if vintage < 7 else "mature")
    # derive need from loan_suitability prior or heuristics
    loan = ctx.prior_outputs.get("loan_suitability", {})
    fac = (loan.get("recommended_facility") or "").lower()
    if "invoice" in fac: need = "invoice_discounting"
    elif "term" in fac: need = "term_loan"
    elif "od" in fac or "cash credit" in fac: need = "working_capital"
    else: need = "term_loan"
    res = execute_tool("search_schemes", {"sector": sector, "stage": stage, "need": need},
                       {**m, "_sector": sector})
    matches = res.get("matches", [])
    top = matches[0]["name"] if matches else "CGTMSE"
    return {
        "summary": (f"Matched {len(matches)} scheme(s)/product(s) for {sector} MSME at {stage} stage, "
                    f"need={need}. Top pick: {top}."),
        "matches": matches,
        "top_pick": top,
        "claims": [Claim(text=f"Top scheme match: {top}", source_agent="scheme_match",
                         source_metric="search_schemes").model_dump()],
    }


# =========================================================================
# 8. COMPLIANCE & EXPLAINABILITY
# =========================================================================
COMPLIANCE_XAI = AgentDef(
    key="compliance_xai", name="Compliance & Explainability Agent", layer=4,
    system_prompt=(
        "You are the Compliance & Explainability Agent. Add RBI/fair-lending regulatory notes and an "
        "explainability layer: every recommendation must be traceable to a deterministic metric. "
        "Flag any data gaps that would require human review. Return JSON matching the schema."),
    build_user=lambda ctx: f"Metrics:\n{_ctx_brief(ctx)}\nPRIOR:\n{_prior_brief(ctx, ['credit_risk','loan_suitability','scheme_match','early_warning'])}",
    tools=["get_early_signals", "get_gst_consistency"],
    output_schema=ComplianceXAIOutput,
    build_fallback=lambda ctx: _comp_fallback(ctx),
    depends_on=["credit_risk", "early_warning", "loan_suitability", "scheme_match"],
)


def _comp_fallback(ctx: AgentContext) -> dict[str, Any]:
    m = ctx.metrics
    reg = [
        "RBI MSME lending guidelines: sanction based on cash-flow & drawing power, not solely on collateral.",
        "CGTMSE coverage applicable for collateral-free limits up to the scheme ceiling.",
        "All recommendations are explainable and traceable to deterministic metrics — no black-box scoring.",
    ]
    if m["gst_missing"] > 0:
        reg.append(f"Data gap: {m['gst_missing']} GST invoices missing filing — human review required before sanction.")
    if m["near_miss_inclusion"]:
        reg.append("Near-miss inclusion: document the cash-flow XAI rationale in the sanction memo.")
    xai = [
        f"Health score {m['health_score']}/100 = weighted sum of 6 published sub-scores (vintage, sector, cash buffer, EMI burden, GST consistency, DSCR).",
        f"Loan-readiness {m['loan_readiness']}/100 derived from DSCR, cash buffer, EMI burden and GST consistency.",
        f"Stress probabilities from a 90-day projected balance path with seasonality adjustment.",
    ]
    return {
        "summary": "Compliance + explainability layer added. All scores are transparent and traceable.",
        "regulatory_notes": reg,
        "explainability_notes": xai,
        "fair_lending_assessment": ("Recommendation is data-driven and sector-blind to protected attributes; "
                                     "decline decisions (if any) must include the XAI rationale and a human-review path."),
        "claims": [Claim(text="All scores traceable to deterministic metrics", source_agent="compliance_xai",
                         source_metric="explainability").model_dump()],
    }


# =========================================================================
# 9. RM COPILOT
# =========================================================================
RM_COPILOT = AgentDef(
    key="rm_copilot", name="RM Copilot Agent", layer=5,
    system_prompt=(
        "You are the Relationship Manager Copilot. Write a banker-facing summary with next-best-actions, "
        "cross-sell opportunities and talking points for the customer meeting. Be concise, action-oriented. "
        "Return JSON matching the schema."),
    build_user=lambda ctx: f"Metrics:\n{_ctx_brief(ctx)}\nPRIOR:\n{_prior_brief(ctx, ['credit_risk','early_warning','loan_suitability','scheme_match'])}",
    tools=["get_health_breakdown", "get_working_capital", "get_early_signals"],
    output_schema=RMCopilotOutput,
    build_fallback=lambda ctx: _rm_fallback(ctx),
    depends_on=["credit_risk", "early_warning", "loan_suitability", "scheme_match"],
)


def _rm_fallback(ctx: AgentContext) -> dict[str, Any]:
    m = ctx.metrics
    loan = ctx.prior_outputs.get("loan_suitability", {})
    scheme = ctx.prior_outputs.get("scheme_match", {})
    ew = ctx.prior_outputs.get("early_warning", {})
    facility = loan.get("recommended_facility", "facility")
    limit = loan.get("suggested_limit_lakh")
    top_scheme = scheme.get("top_pick", "")
    nba = []
    if limit:
        nba.append(f"Offer {facility} of ₹{limit} lakh — backed by cash-flow XAI.")
    if top_scheme:
        nba.append(f"Pitch {top_scheme} for collateral-free/subsidised access.")
    if m["gst_missing"] > 0:
        nba.append("Ask customer to reconcile missing GST filings before sanction.")
    nba.append("Schedule 30-day review on cash buffer trajectory.")
    cross = ["Current/savings account salary-banking", "Axis: merchant UDI / POS acquiring", "Trade finance / FX (if export)"]
    if m["stated_turnover_lakh"] >= 100: cross.append("Capex term loan for expansion")
    talking = [
        f"Health score {m['health_score']}/100; loan-readiness {m['loan_readiness']}/100.",
        f"Cash buffer {m['cash_buffer_days']:.0f} days; DSCR {m['dscr']:.2f}.",
        (f"Near-miss inclusion case — explain why UdyamMitra recommends despite traditional gate."
         if m["near_miss_inclusion"] else "Healthy credit indicators."),
    ]
    risk = ("Low") if m["loan_readiness"] >= 70 else ("Moderate" if m["loan_readiness"] >= 45 else "Elevated")
    return {
        "summary": (f"Banker brief for {ctx.msme.get('name')}: readiness {m['loan_readiness']}/100, "
                    f"recommended {facility}" + (f" ₹{limit} lakh" if limit else "") +
                    f". Bank risk: {risk}."),
        "next_best_actions": nba,
        "cross_sell_opportunities": cross,
        "talking_points": talking,
        "risk_for_bank": f"{risk} — " + ("monitor cash buffer." if risk != "Low" else "standard monitoring."),
        "claims": [Claim(text="RM brief assembled from prior agent outputs", source_agent="rm_copilot",
                         source_metric="loan_readiness").model_dump()],
    }


# =========================================================================
# 10. REPORT (bilingual, provenance)
# =========================================================================
REPORT = AgentDef(
    key="report", name="Report Agent", layer=6,
    system_prompt=(
        "You are the Report Agent. Assemble the final bilingual explainable report: an OWNER view "
        "(simple Hindi + English, encouraging, no raw pessimistic risk phrasing) and an RM/banker view "
        "(English, detailed, with risk and next-best-actions). Collect provenance for every claim. "
        "Return JSON matching the schema."),
    build_user=lambda ctx: (f"Metrics:\n{_ctx_brief(ctx)}\nALL PRIOR AGENT OUTPUTS (summarise into the report):\n"
                            + json.dumps({k: v.get("summary", str(v))[:300] for k, v in ctx.prior_outputs.items()
                                          if isinstance(v, dict)}, ensure_ascii=False)),
    tools=[],
    output_schema=ReportOutput,
    build_fallback=lambda ctx: _report_fallback(ctx),
    depends_on=["credit_risk", "early_warning", "loan_suitability", "scheme_match", "compliance_xai", "rm_copilot"],
)


def _report_fallback(ctx: AgentContext) -> dict[str, Any]:
    m = ctx.metrics
    loan = ctx.prior_outputs.get("loan_suitability", {})
    scheme = ctx.prior_outputs.get("scheme_match", {})
    rm = ctx.prior_outputs.get("rm_copilot", {})
    facility = loan.get("recommended_facility", "a suitable credit facility")
    limit = loan.get("suggested_limit_lakh")
    top_scheme = scheme.get("top_pick", "")
    hs = m["health_score"]; lr = m["loan_readiness"]

    en_owner = (f"Your business health score is {hs}/100 and loan-readiness is {lr}/100. "
                f"We recommend {facility}" + (f" around ₹{limit} lakh" if limit else "") +
                (f", and the {top_scheme} scheme could help you get collateral-free funding." if top_scheme else ".")
                + " Keep your GST filings consistent to improve eligibility.")
    hi_owner = (f"आपके व्यवसाय की स्वास्थ्य स्कोर {hs}/100 और लोन-तत्परता {lr}/100 है। "
                f"हम {facility}" + (f" लगभग ₹{limit} लाख" if limit else "") +
                (" की सिफारिश करते हैं, और " + top_scheme + " योजना आपको बिना गिरवी के वित्त दिला सकती है।"
                 if top_scheme else " की सिफारिश करते हैं।")
                + " अपनी GST रिटर्न नियमित भरें ताकि पात्रता बेहतर हो।")

    rm_summary = (f"{ctx.msme.get('name')} — loan-readiness {lr}/100, health {hs}/100. "
                  f"Recommended: {facility}" + (f" ₹{limit} lakh" if limit else "") +
                  (f"; scheme: {top_scheme}." if top_scheme else ".") +
                  f" Cash buffer {m['cash_buffer_days']:.0f} days, DSCR {m['dscr']:.2f}, "
                  f"EMI burden {m['emi_burden_ratio']*100:.0f}%, GST consistency {m['gst_consistency']*100:.0f}%."
                  + (" Near-miss inclusion case — sanction with documented XAI rationale." if m["near_miss_inclusion"] else ""))
    recs = []
    if limit: recs.append(f"{facility} ₹{limit} lakh")
    if top_scheme: recs.append(f"Apply: {top_scheme}")
    if m["gst_missing"] > 0: recs.append(f"Reconcile {m['gst_missing']} missing GST invoices")
    recs.append("30-day cash-buffer review")

    prov = []
    for a in ["profile", "transaction", "forecast", "credit_risk", "early_warning", "loan_suitability", "scheme_match", "compliance_xai", "rm_copilot"]:
        o = ctx.prior_outputs.get(a)
        if o and o.get("claims"):
            for c in o["claims"][:1]:
                prov.append(c)
    return {
        "title": f"UdyamMitra AI — Credit Intelligence Report: {ctx.msme.get('name')}",
        "one_line": f"Health {hs}/100 · Loan-readiness {lr}/100 · Recommended: {facility}",
        "owner": {"en": en_owner, "hi": hi_owner},
        "rm": {
            "summary": rm_summary,
            "next_best_actions": rm.get("next_best_actions", []),
            "cross_sell": rm.get("cross_sell_opportunities", []),
            "risk_for_bank": rm.get("risk_for_bank", ""),
            "regulatory_notes": ctx.prior_outputs.get("compliance_xai", {}).get("regulatory_notes", []),
            "early_warning_signals": m["early_warning_signals"],
            "sub_scores": m["sub_scores"],
        },
        "health_score": hs,
        "loan_readiness": lr,
        "recommendations": recs,
        "provenance": prov,
    }


# =========================================================================
# Registry + DAG
# =========================================================================
AGENTS: dict[str, AgentDef] = {
    a.key: a for a in [PROFILE, TRANSACTION, FORECAST, CREDIT_RISK, EARLY_WARNING,
                       LOAN_SUITABILITY, SCHEME_MATCH, COMPLIANCE_XAI, RM_COPILOT, REPORT]
}

# Execution layers (each layer's agents run in parallel).
DAG_LAYERS: list[list[str]] = [
    ["profile", "transaction"],
    ["forecast"],
    ["credit_risk", "early_warning"],
    ["loan_suitability", "scheme_match"],
    ["compliance_xai"],
    ["rm_copilot"],
    ["report"],
]