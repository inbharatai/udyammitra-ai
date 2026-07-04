"""Connector base interface + normalised result shape."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol


@dataclass
class ConnectorResult:
    """Normalised payload returned by every alternate-data connector.

    `records` is source-specific but always a list of plain dicts the scoring
    core can consume. `provenance` is surfaced to the explainability agent so
    every number traces back to a real source (or an honest "seed/synthetic").
    """

    source: str                     # "gst" | "aa" | "upi" | "epfo"
    msme_id: str
    fetched_at: str                  # ISO-8601 UTC
    live: bool                       # False when seed/synthetic/spec-only
    records: list[dict[str, Any]] = field(default_factory=list)
    notes: str = ""                  # e.g. "GSTR-2B, 24 months"
    provenance: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "msme_id": self.msme_id,
            "fetched_at": self.fetched_at,
            "live": self.live,
            "records": self.records,
            "notes": self.notes,
            "provenance": self.provenance,
        }


class AlternateDataConnector(Protocol):
    """Every connector implements `fetch(msme_id)` → ConnectorResult."""

    source: str

    def fetch(self, msme_id: str) -> ConnectorResult: ...


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()