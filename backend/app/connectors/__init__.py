"""Alternate-data connectors (Problem Statement 3).

Each connector fetches one alternate-data source for an MSME and returns a
normalised payload that feeds the deterministic scoring core
(`app.scoring.metrics`). The shape is intentionally uniform so a new source
(UPI, EPFO, electricity, GST, AA…) is a drop-in.

Status — honest:
  * GST  — spec-ready. Live pull requires a GSP/ASP partner credential
           (ClearTax / Masterso / TaxPro). Skeleton returns NotImplementedError
           until GSP_ASP_TOKEN is configured.
  * AA   — spec-ready. Live pull goes through the Sahamati AA gateway with a
           customer consent handle (FIU fetch). Skeleton raises until wired.
  * UPI  — UPI has no separate public lender API. UPI transactions surface
           inside bank-statement data fetched via AA; this connector parses
           AA-delivered statement payloads for UPI rows.
  * EPFO — gated. EPFO does not expose a clean open API to third parties; use
           scoped employer-side access where legitimate, else declared+verify.
           Skeleton raises; do not fake live EPFO pulls.

These are ingestion primitives, not LLM agents — they run out-of-band
(EventBridge → SQS → Lambda in the AWS stack) and write to Aurora + S3.
"""
from app.connectors.base import AlternateDataConnector, ConnectorResult
from app.connectors.gst import GSTConnector
from app.connectors.aa import AccountAggregatorConnector
from app.connectors.upi import UPIConnector
from app.connectors.epfo import EPFOConnector

__all__ = [
    "AlternateDataConnector",
    "ConnectorResult",
    "GSTConnector",
    "AccountAggregatorConnector",
    "UPIConnector",
    "EPFOConnector",
]