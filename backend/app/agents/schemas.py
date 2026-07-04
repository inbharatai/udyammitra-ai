"""Pydantic output schemas for each agent (typed agent-to-agent contracts)."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict


class Claim(BaseModel):
    """An explainable claim with provenance — the XAI backbone."""
    model_config = ConfigDict(extra="allow")
    text: str
    source_agent: str = ""
    source_metric: str = ""


class ProfileOutput(BaseModel):
    model_config = ConfigDict(extra="allow")
    summary: str
    sector_outlook: str
    vintage_assessment: str
    key_facts: list[str] = []
    claims: list[Claim] = []


class TransactionOutput(BaseModel):
    model_config = ConfigDict(extra="allow")
    summary: str
    revenue_pattern: str
    expense_pattern: str
    emi_burden_assessment: str
    seasonality_assessment: str
    gst_consistency_assessment: str
    anomalies: list[str] = []
    claims: list[Claim] = []


class ForecastOutput(BaseModel):
    model_config = ConfigDict(extra="allow")
    summary: str
    stress_30d: str
    stress_60d: str
    stress_90d: str
    confidence: str
    key_risk: str
    claims: list[Claim] = []


class CreditRiskOutput(BaseModel):
    model_config = ConfigDict(extra="allow")
    summary: str
    loan_readiness_indicator: str
    readiness_value: Optional[float] = None
    strengths: list[str] = []
    weaknesses: list[str] = []
    bureau_disclaimer: str = ""
    claims: list[Claim] = []


class EarlyWarningOutput(BaseModel):
    model_config = ConfigDict(extra="allow")
    summary: str
    signals: list[dict[str, Any]] = []
    top_action: str
    claims: list[Claim] = []


class LoanSuitabilityOutput(BaseModel):
    model_config = ConfigDict(extra="allow")
    summary: str
    recommended_facility: str
    suggested_limit_lakh: Optional[float] = None
    rationale: str
    alternatives: list[str] = []
    claims: list[Claim] = []


class SchemeMatchOutput(BaseModel):
    model_config = ConfigDict(extra="allow")
    summary: str
    matches: list[dict[str, Any]] = []
    top_pick: str
    claims: list[Claim] = []


class ComplianceXAIOutput(BaseModel):
    model_config = ConfigDict(extra="allow")
    summary: str
    regulatory_notes: list[str] = []
    explainability_notes: list[str] = []
    fair_lending_assessment: str
    claims: list[Claim] = []


class RMCopilotOutput(BaseModel):
    model_config = ConfigDict(extra="allow")
    summary: str
    next_best_actions: list[str] = []
    cross_sell_opportunities: list[str] = []
    talking_points: list[str] = []
    risk_for_bank: str
    claims: list[Claim] = []


class OwnerGuidance(BaseModel):
    model_config = ConfigDict(extra="allow")
    en: str
    hi: str


class ReportOutput(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: str
    one_line: str
    owner: dict[str, Any]  # {en:..., hi:...}
    rm: dict[str, Any]     # banker-facing (English)
    health_score: Optional[float] = None
    loan_readiness: Optional[float] = None
    recommendations: list[str] = []
    provenance: list[Claim] = []


# Registry of (agent_key -> output model)
OUTPUT_SCHEMAS = {
    "profile": ProfileOutput,
    "transaction": TransactionOutput,
    "forecast": ForecastOutput,
    "credit_risk": CreditRiskOutput,
    "early_warning": EarlyWarningOutput,
    "loan_suitability": LoanSuitabilityOutput,
    "scheme_match": SchemeMatchOutput,
    "compliance_xai": ComplianceXAIOutput,
    "rm_copilot": RMCopilotOutput,
    "report": ReportOutput,
}