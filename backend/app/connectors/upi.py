"""UPI connector — parses UPI rows out of AA-delivered bank statements.

UPI has no separate public lender data API. UPI transactions surface inside
the bank-statement payload fetched through the Account Aggregator connector.
This connector therefore consumes an AA statement payload (or a raw statement
file) and emits normalised UPI transaction records.

Until the AA connector is wired, `fetch` raises NotImplementedError.
"""
from __future__ import annotations

from app.connectors.base import ConnectorResult, _utcnow_iso
from app.core.config import settings


class UPIConnector:
    source = "upi"

    def fetch(self, msme_id: str, statement_payload: list[dict] | None = None) -> ConnectorResult:
        if not statement_payload:
            # No statement payload → would come from AccountAggregatorConnector.
            raise NotImplementedError(
                "UPI data arrives via AA-delivered bank statements; pass "
                "statement_payload from AccountAggregatorConnector once wired."
            )
        # When wired: scan statement rows for UPI refs (UPI/…@vpa), normalise
        # into Transaction records (category heuristics: salary/revenue/emi),
        # and emit provenance pointing back to the AA consent handle.
        raise NotImplementedError("UPI statement-parse path not yet implemented.")