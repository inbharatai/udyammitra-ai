"""Account Aggregator (AA) connector — Sahamati gateway, consent-driven.

Live pull requires (a) a registered FIU app on the Sahamati ecosystem and
(b) a customer consent handle. Until SAHAMATI_AA_BASE_URL +
SAHAMATI_AA_CLIENT_ID are configured, `fetch` raises NotImplementedError and
the app falls back to seeded bank-statement transactions.

This is also the pipe through which UPI rows arrive: UPI has no separate
public lender API; UPI transactions surface inside bank-statement data
fetched via AA. See app.connectors.upi.
"""
from __future__ import annotations

from app.connectors.base import ConnectorResult, _utcnow_iso
from app.core.config import settings


class AccountAggregatorConnector:
    source = "aa"

    def fetch(self, msme_id: str, consent_handle: str | None = None) -> ConnectorResult:
        base = (settings.sahamati_aa_base_url or "").strip()
        client_id = (settings.sahamati_aa_client_id or "").strip()
        if not base or not client_id:
            raise NotImplementedError(
                "AA live pull is spec-ready but not wired: set SAHAMATI_AA_BASE_URL "
                "and SAHAMATI_AA_CLIENT_ID, and pass a valid consent_handle. "
                "Falling back to seeded bank-statement transactions."
            )
        if not consent_handle:
            raise NotImplementedError(
                "AA fetch requires a customer consent handle (FIU consent flow)."
            )
        # When wired: discover AA → consent redirect → FIU fetch (bank
        # statements, FD, recurring deposits) → normalise into Transaction
        # rows → raw payload to S3, structured rows to Aurora.
        raise NotImplementedError("AA live fetch path not yet implemented.")