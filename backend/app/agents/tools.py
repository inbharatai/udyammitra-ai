"""Function-calling tools agents use to pull deterministic metrics & schemes.

These tools are the 'agency' — an agent decides which metric to query and
reasons over the returned numbers instead of being pre-stuffed with context.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from app.core.config import SEED_DIR

_SCHEMES_CACHE: list[dict[str, Any]] | None = None


def load_schemes() -> list[dict[str, Any]]:
    global _SCHEMES_CACHE
    if _SCHEMES_CACHE is None:
        p = Path(SEED_DIR) / "schemes.json"
        _SCHEMES_CACHE = json.loads(p.read_text(encoding="utf-8")).get("schemes", [])
    return _SCHEMES_CACHE


# --- Tool implementations (operate on a metrics dict `m`) ---

def t_emi_burden(m: dict, **_kw) -> dict:
    return {"emi_burden_ratio": m["emi_burden_ratio"],
            "assessment": "high" if m["emi_burden_ratio"] > 0.30 else ("moderate" if m["emi_burden_ratio"] > 0.15 else "low")}


def t_seasonality(m: dict, **_kw) -> dict:
    return {"seasonality_index": m["seasonality_index"],
            "assessment": "high" if m["seasonality_index"] > 0.35 else ("moderate" if m["seasonality_index"] > 0.20 else "low")}


def t_cash_buffer_days(m: dict, **_kw) -> dict:
    return {"cash_buffer_days": m["cash_buffer_days"],
            "assessment": "critical" if m["cash_buffer_days"] < 14 else ("low" if m["cash_buffer_days"] < 21 else ("adequate" if m["cash_buffer_days"] < 45 else "strong"))}


def t_dscr(m: dict, **_kw) -> dict:
    return {"dscr": m["dscr"], "has_debt": m["avg_monthly_emi"] > 0,
            "assessment": "strong" if m["dscr"] >= 1.5 else ("adequate" if m["dscr"] >= 1.2 else ("weak" if m["dscr"] >= 1.0 else "stressed"))}


def t_stress_probability(m: dict, horizon: str = "60d", **_kw) -> dict:
    sp = m["stress_probabilities"]
    return {"horizon": horizon, "probability": sp.get(horizon, sp.get("60d", 0)),
            "projection_min_balance": m["projection_min_balance"],
            "current_balance": m["current_balance"]}


def t_cash_gap(m: dict, window_days: int = 30, **_kw) -> dict:
    daily_burn = (m["avg_monthly_opex"] + m["avg_monthly_emi"]) / 30.0
    covered_days = (m["current_balance"] / daily_burn) if daily_burn > 0 else 999
    gap_days = max(window_days - covered_days, 0)
    return {"window_days": window_days, "covered_days": round(covered_days, 0),
            "gap_days": round(gap_days, 0), "estimated_gap_lakh": round(gap_days * daily_burn / 1e5, 2)}


def t_health_breakdown(m: dict, **_kw) -> dict:
    return {"health_score": m["health_score"], "loan_readiness": m["loan_readiness"],
            "sub_scores": m["sub_scores"]}


def t_working_capital(m: dict, **_kw) -> dict:
    return {"working_capital_gap_lakh": m["working_capital_gap_lakh"],
            "od_cc_limit_lakh": m["od_cc_limit_lakh"],
            "invoice_discounting_eligible": m["invoice_discounting_eligible"],
            "current_ratio": m["current_ratio"]}


def t_gst_consistency(m: dict, **_kw) -> dict:
    return {"gst_consistency": m["gst_consistency"], "gst_delayed": m["gst_delayed"],
            "gst_missing": m["gst_missing"], "invoice_count": m["invoice_count"]}


def t_early_signals(m: dict, **_kw) -> dict:
    return {"signals": m["early_warning_signals"], "near_miss_inclusion": m["near_miss_inclusion"],
            "naive_bureau_eligible": m["naive_bureau_eligible"]}


def t_search_schemes(m: dict, sector: str = "", stage: str = "", need: str = "", **_kw) -> dict:
    msme_sector = m.get("_sector", "")
    schemes = load_schemes()
    scored = []
    need_l = need.lower()
    for s in schemes:
        if sector and s["sectors"] != ["all"] and sector not in s["sectors"] and msme_sector not in s["sectors"]:
            continue
        score = 0
        if need_l:
            if need_l in s["type"]: score += 3
            if need_l in s["purpose"].lower(): score += 2
            for h in s["highlights"]:
                if need_l in h.lower(): score += 1
        if msme_sector in s["sectors"]: score += 2
        scored.append((score, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [s for _, s in scored[:5]]
    return {"matches": [{"code": s["code"], "name": s["name"], "type": s["type"],
                         "purpose": s["purpose"], "highlights": s["highlights"],
                         "best_for": s["best_for"]} for s in top]}


# --- OpenAI tool schemas (function definitions) ---
TOOL_IMPLS: dict[str, Callable[..., dict]] = {
    "get_emi_burden": t_emi_burden,
    "get_seasonality": t_seasonality,
    "get_cash_buffer_days": t_cash_buffer_days,
    "get_dscr": t_dscr,
    "get_stress_probability": t_stress_probability,
    "get_cash_gap": t_cash_gap,
    "get_health_breakdown": t_health_breakdown,
    "get_working_capital": t_working_capital,
    "get_gst_consistency": t_gst_consistency,
    "get_early_signals": t_early_signals,
    "search_schemes": t_search_schemes,
}

ALL_TOOL_SCHEMAS = [
    {"type": "function", "function": {"name": "get_emi_burden", "description": "Get the MSME's EMI-to-revenue burden ratio and assessment.",
     "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_seasonality", "description": "Get the revenue seasonality index (coefficient of variation).",
     "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_cash_buffer_days", "description": "Get days of operating cash the MSME has on hand.",
     "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_dscr", "description": "Get the seasonality-adjusted Debt Service Coverage Ratio.",
     "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_stress_probability", "description": "Get projected cash-flow stress probability for a horizon.",
     "parameters": {"type": "object", "properties": {"horizon": {"type": "string", "enum": ["30d", "60d", "90d"]}}}}},
    {"type": "function", "function": {"name": "get_cash_gap", "description": "Compute the cash gap (uncovered days) over a forward window.",
     "parameters": {"type": "object", "properties": {"window_days": {"type": "integer", "default": 30}}}}},
    {"type": "function", "function": {"name": "get_health_breakdown", "description": "Get the health score, loan readiness and sub-score breakdown.",
     "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_working_capital", "description": "Get working-capital gap, suggested OD/CC limit and invoice-discounting eligibility.",
     "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_gst_consistency", "description": "Get GST 2A/2B filing consistency stats.",
     "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_early_signals", "description": "Get early-warning signals and near-miss inclusion flag.",
     "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "search_schemes", "description": "Search government schemes & IDBI MSME products by sector/stage/need.",
     "parameters": {"type": "object", "properties": {"sector": {"type": "string"}, "stage": {"type": "string"}, "need": {"type": "string", "description": "e.g. working_capital, term_loan, invoice_discounting, advisory"}}}}},
]


def schemas_for(names: list[str]) -> list[dict]:
    by_name = {s["function"]["name"]: s for s in ALL_TOOL_SCHEMAS}
    return [by_name[n] for n in names if n in by_name]


def execute_tool(name: str, arguments: dict[str, Any], m: dict) -> dict:
    fn = TOOL_IMPLS.get(name)
    if not fn:
        return {"error": f"unknown tool {name}"}
    try:
        return fn(m, **arguments)
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}