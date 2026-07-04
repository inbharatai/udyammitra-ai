"""EPFO connector — scoped/gated employment data.

EPFO does not expose a clean open API to third parties. Legitimate access is
scoped/employer-side via the EPFO Unified Portal. Where you cannot pull live,
treat payroll/employment as declared-and-verify rather than fabricating a
live pull. Until EPFO_BASE_URL is configured and a legitimate access path is
agreed, `fetch` raises NotImplementedError.

Be honest on the slide: EPFO is declared-verify in the prototype, not live.
"""
from __future__ import annotations

from app.connectors.base import ConnectorResult, _utcnow_iso
from app.core.config import settings


class EPFOConnector:
    source = "epfo"

    def fetch(self, msme_id: str, establishment_id: str | None = None) -> ConnectorResult:
        base = (settings.epfo_base_url or "").strip()
        if not base:
            raise NotImplementedError(
                "EPFO is gated/scoped; no clean open third-party API. Set "
                "EPFO_BASE_URL only with a legitimate access path. Prototype "
                "treats payroll as declared-and-verify, not live-pulled."
            )
        if not establishment_id:
            raise NotImplementedError("EPFO fetch requires an establishment id.")
        # When wired (scoped access only): fetch member count + contribution
        # history → derive payroll stability signal → feed scoring core.
        raise NotImplementedError("EPFO live fetch path not yet implemented.")