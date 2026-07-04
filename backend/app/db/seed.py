"""Deterministic synthetic MSME data generator.

Produces 9 realistic Indian MSMEs across sectors with 24 months of
transactions + GST invoices, then persists to SQLite and writes JSON
seeds to data/seed/. Idempotent (wipes + re-inserts on each run).

Realism baked in:
  * Udyam Registration Number format  UDYAM-<state>-00-0000000
  * GSTIN format  <state><PAN10><E><Z><checksum>
  * Rounded-to-100 invoice values, delayed/missing GST filings,
    one festival-season spike + one lean month, salary-day clustering,
    occasional vendor refunds.
  * One engineered "near-miss inclusion" hero MSME (Bharat Textiles)
    that naive bureau logic declines but UdyamMitra flags OD-CC-eligible.
"""
from __future__ import annotations

import json
import random
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.config import SEED_DIR
from app.db.database import dumps, session_scope
from app.db.models import GSTInvoice, MSME, Transaction

# Deterministic.
RNG = random.Random(20260703)

MONTHS = 24
START = date(2024, 7, 1)

# State codes (GST first two digits).
STATES = {
    "GJ": ("Gujarat", "24"),
    "MH": ("Maharashtra", "27"),
    "TN": ("Tamil Nadu", "33"),
    "RJ": ("Rajasthan", "08"),
    "WB": ("West Bengal", "19"),
    "KA": ("Karnataka", "29"),
    "UP": ("Uttar Pradesh", "09"),
    "DL": ("Delhi", "07"),
}

PAN_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
GST_RATES = [0.05, 0.12, 0.18]


def _pan() -> str:
    return "".join(RNG.choice(PAN_CHARS) for _ in range(10))


def _gstin(state_code: str) -> str:
    pan = _pan()
    entity = RNG.choice(["E", "C", "F", "P"])
    # Plausible checksum char (not algorithmically valid — looks real).
    check = RNG.choice("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    return f"{state_code}{pan}{entity}Z{check}"


def _udyam(state_code: str, n: int) -> str:
    return f"UDYAM-{state_code}-00-{n:07d}"


def _invoice_number(seq: int) -> str:
    return f"INV/{seq:04d}/{RNG.choice(['24-25', '25-26'])}"


# ---- MSME definitions ----
MSME_DEFS: list[dict[str, Any]] = [
    {
        "id": "MSME-001", "name": "Bharat Textiles", "sector": "Textile",
        "sub_sector": "Garment manufacturing", "state_key": "TN", "city": "Tiruppur",
        "vintage_years": 3.2, "entity_type": "Proprietorship",
        "annual_turnover_lakh": 85.0, "is_near_miss": True,
        "seasonality": "festival_q3", "emi_lakh_monthly": 0.85, "margin": 0.14,
        "note": "Near-miss hero: thin margins + seasonal dip → naive logic declines; OD-CC eligible.",
    },
    {
        "id": "MSME-002", "name": "Shree Food Processing", "sector": "Food Processing",
        "sub_sector": "Spices & masala", "state_key": "KA", "city": "Bengaluru",
        "vintage_years": 5.0, "entity_type": "Pvt Ltd",
        "annual_turnover_lakh": 220.0, "is_near_miss": False,
        "seasonality": "festival_q3", "emi_lakh_monthly": 1.6, "margin": 0.19,
    },
    {
        "id": "MSME-003", "name": "Patel Steel Works", "sector": "Manufacturing",
        "sub_sector": "Light engineering", "state_key": "GJ", "city": "Rajkot",
        "vintage_years": 7.5, "entity_type": "Partnership",
        "annual_turnover_lakh": 410.0, "is_near_miss": False,
        "seasonality": "flat", "emi_lakh_monthly": 3.2, "margin": 0.16,
    },
    {
        "id": "MSME-004", "name": "Krishna Agro Traders", "sector": "Agriculture",
        "sub_sector": "Seeds & inputs trading", "state_key": "MH", "city": "Pune",
        "vintage_years": 4.0, "entity_type": "Proprietorship",
        "annual_turnover_lakh": 60.0, "is_near_miss": False,
        "seasonality": "kharif_rabi", "emi_lakh_monthly": 0.0, "margin": 0.12,
    },
    {
        "id": "MSME-005", "name": "Sunrise Retail Mart", "sector": "Retail Trading",
        "sub_sector": "Grocery & FMCG", "state_key": "RJ", "city": "Jaipur",
        "vintage_years": 2.5, "entity_type": "Proprietorship",
        "annual_turnover_lakh": 130.0, "is_near_miss": False,
        "seasonality": "festival_q3", "emi_lakh_monthly": 0.7, "margin": 0.08,
    },
    {
        "id": "MSME-006", "name": "Maa Durga Handicrafts", "sector": "Handicrafts",
        "sub_sector": "Home decor exports", "state_key": "WB", "city": "Kolkata",
        "vintage_years": 6.0, "entity_type": "Partnership",
        "annual_turnover_lakh": 95.0, "is_near_miss": False,
        "seasonality": "export_q4", "emi_lakh_monthly": 1.1, "margin": 0.22,
    },
    {
        "id": "MSME-007", "name": "TechNova IT Services", "sector": "Services",
        "sub_sector": "IT & SaaS implementation", "state_key": "KA", "city": "Bengaluru",
        "vintage_years": 1.8, "entity_type": "Pvt Ltd",
        "annual_turnover_lakh": 180.0, "is_near_miss": False,
        "seasonality": "flat", "emi_lakh_monthly": 0.0, "margin": 0.28,
    },
    {
        "id": "MSME-008", "name": "GreenLeaf Paper Products", "sector": "Manufacturing",
        "sub_sector": "Eco packaging", "state_key": "UP", "city": "Noida",
        "vintage_years": 3.8, "entity_type": "Pvt Ltd",
        "annual_turnover_lakh": 150.0, "is_near_miss": False,
        "seasonality": "flat", "emi_lakh_monthly": 1.3, "margin": 0.17,
    },
    {
        "id": "MSME-009", "name": "Delhi Auto Components", "sector": "Manufacturing",
        "sub_sector": "Auto parts supplier", "state_key": "DL", "city": "Delhi",
        "vintage_years": 9.0, "entity_type": "Pvt Ltd",
        "annual_turnover_lakh": 520.0, "is_near_miss": False,
        "seasonality": "flat", "emi_lakh_monthly": 4.1, "margin": 0.15,
    },
]


def _seasonal_factor(month_index: int, kind: str) -> float:
    """Monthly multiplier around 1.0 by seasonality type."""
    m = month_index % 12  # 0=Jul ... 11=Jun
    if kind == "festival_q3":
        # Sep–Nov (idx 2,3,4) festival surge; Feb lean.
        base = {0: 0.95, 1: 0.90, 2: 1.35, 3: 1.50, 4: 1.40, 5: 0.95,
                6: 0.85, 7: 0.90, 8: 1.05, 9: 1.05, 10: 1.10, 11: 1.00}
    elif kind == "kharif_rabi":
        # Jun–Oct kharif, Nov–Feb rabi peaks.
        base = {0: 1.20, 1: 0.70, 2: 0.75, 3: 0.90, 4: 1.10, 5: 1.30,
                6: 1.40, 7: 1.20, 8: 0.90, 9: 0.80, 10: 1.00, 11: 1.25}
    elif kind == "export_q4":
        # Oct–Jan export peak.
        base = {0: 0.90, 1: 0.85, 2: 1.10, 3: 1.40, 4: 1.45, 5: 1.20,
                6: 0.80, 7: 0.85, 8: 0.90, 9: 1.00, 10: 1.10, 11: 0.95}
    else:  # flat
        base = {i: 1.0 for i in range(12)}
    return base[m]


def _round100(x: float) -> float:
    return round(x / 100.0) * 100.0


def _month_dates(year: int, month: int, n: int) -> list[str]:
    """n dates within the given month, clustered on salary/payment days."""
    first = date(year, month, 1)
    days_in_month = (date(year + (1 if month == 12 else 0), (month % 12) + 1, 1) - first).days
    dates = []
    for _ in range(n):
        # Cluster around 1st, 7th, 15th, 28th (salary/vendor days)
        anchor = RNG.choice([1, 5, 7, 10, 15, 20, 25, 28])
        d = min(anchor + RNG.randint(-2, 2), days_in_month)
        d = max(d, 1)
        dates.append((first + timedelta(days=d - 1)).isoformat())
    return sorted(dates)


def _generate_transactions(defn: dict[str, Any]) -> list[dict[str, Any]]:
    """Build 24 months of transactions for an MSME."""
    annual = defn["annual_turnover_lakh"] * 1e5  # to rupees
    monthly_rev_base = annual / 12.0
    emi_monthly = defn["emi_lakh_monthly"] * 1e5
    margin = defn["margin"]
    season = defn["seasonality"]
    is_near_miss = defn.get("is_near_miss", False)

    txns: list[dict[str, Any]] = []
    for i in range(MONTHS):
        y, m = (START.year + (START.month - 1 + i) // 12), ((START.month - 1 + i) % 12) + 1
        sf = _seasonal_factor(i, season)
        # Noise: ±8% (± more for near-miss to create a stressed month).
        noise = RNG.uniform(-0.08, 0.08)
        if is_near_miss and i in (16, 17):  # a lean/stressed stretch
            sf *= 0.62
            noise = RNG.uniform(-0.12, -0.04)
        month_rev = monthly_rev_base * sf * (1 + noise)
        # Revenue: 3-7 sales receipts rounded to 100.
        n_receipts = RNG.randint(3, 7)
        per = _round100(month_rev / n_receipts)
        for d in _month_dates(y, m, n_receipts):
            txns.append({
                "date": d, "description": "Sales receipt",
                "category": "revenue", "amount": round(per, 2),
                "channel": RNG.choice(["UPI", "RTGS", "NEFT", "IMPS"]),
                "counterparty": RNG.choice(["Trade buyer", "Wholesaler", "Export client", "Retail chain"]),
            })
        # --- Cost allocation: vendor + salary + rent + utility + gst SUM to
        #     revenue*(1-margin) so net operating cash flow = margin*revenue.
        #     EMI is separate (debt service paid out of the operating surplus).
        gst_out = round(_round100(month_rev * 0.09), 2)
        salary = round(_round100(month_rev * RNG.uniform(0.08, 0.13)), 2)
        rent = round(_round100(month_rev * RNG.uniform(0.025, 0.04)), 2)
        utility = round(_round100(month_rev * RNG.uniform(0.015, 0.025)), 2)
        cost_pool = month_rev * (1 - margin)
        vendor_total = max(cost_pool - gst_out - salary - rent - utility, month_rev * 0.1)
        n_vendor = RNG.randint(2, 4)
        per_v = _round100(vendor_total / n_vendor)
        for d in _month_dates(y, m, n_vendor):
            txns.append({
                "date": d, "description": "Raw material / vendor payment",
                "category": "expense", "amount": -round(per_v, 2),
                "channel": RNG.choice(["RTGS", "NEFT", "UPI"]),
                "counterparty": RNG.choice(["Supplier A", "Vendor B", "Raw material co", "Logistics"]),
            })
        # Salary (1st of month)
        txns.append({
            "date": date(y, m, 1).isoformat(), "description": "Staff salary",
            "category": "salary", "amount": -salary,
            "channel": "NEFT", "counterparty": "Payroll",
        })
        # Rent (7th) and utility (12th)
        txns.append({
            "date": date(y, m, 7).isoformat(), "description": "Workshop/office rent",
            "category": "expense", "amount": -rent, "channel": "NEFT", "counterparty": "Landlord",
        })
        txns.append({
            "date": date(y, m, 12).isoformat(), "description": "Electricity & utilities",
            "category": "expense", "amount": -utility,
            "channel": "UPI", "counterparty": "Power distribution co",
        })
        # EMI on 5th
        if emi_monthly > 0:
            txns.append({
                "date": date(y, m, 5).isoformat(), "description": "Term loan EMI",
                "category": "emi", "amount": -round(_round100(emi_monthly), 2),
                "channel": "RTGS", "counterparty": "IDBI Bank",
            })
            # One delayed EMI for near-miss in a stressed month
            if is_near_miss and i == 17 and RNG.random() < 0.6:
                txns.append({
                    "date": date(y, m, 19).isoformat(), "description": "Term loan EMI (delayed)",
                    "category": "emi", "amount": -round(_round100(emi_monthly), 2),
                    "channel": "RTGS", "counterparty": "IDBI Bank",
                })
        # GST outflow (filing lag)
        txns.append({
            "date": (date(y, m, 20) + timedelta(days=RNG.randint(0, 5))).isoformat(),
            "description": "GST output tax payment", "category": "gst",
            "amount": -gst_out, "channel": "RTGS", "counterparty": "GSTN",
        })
        # Occasional vendor refund (credit)
        if RNG.random() < 0.10:
            txns.append({
                "date": _month_dates(y, m, 1)[0], "description": "Vendor refund / reversal",
                "category": "refund", "amount": round(_round100(RNG.uniform(2000, 12000)), 2),
                "channel": "UPI", "counterparty": "Supplier A",
            })
    # sort by date
    txns.sort(key=lambda t: t["date"])
    return txns


def _generate_invoices(defn: dict[str, Any], txns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """GST sales invoices derived from revenue transactions."""
    state_name, state_code = STATES[defn["state_key"]]
    party_gstin = _gstin(state_code)
    invoices: list[dict[str, Any]] = []
    seq = 1
    rev_txns = [t for t in txns if t["category"] == "revenue"]
    # One invoice per ~2 revenue receipts.
    for idx in range(0, len(rev_txns), 2):
        t = rev_txns[idx]
        total = _round100(t["amount"] * RNG.uniform(1.0, 1.2))
        rate = RNG.choice(GST_RATES)
        taxable = round(total / (1 + rate), 2)
        gst = round(total - taxable, 2)
        # Filing realism: ~85% filed, ~10% delayed, ~5% missing
        r = RNG.random()
        filing = "filed" if r < 0.85 else ("delayed" if r < 0.95 else "missing")
        invoices.append({
            "invoice_number": _invoice_number(seq),
            "invoice_date": t["date"],
            "party_gstin": party_gstin if filing != "missing" else "",
            "party_name": RNG.choice(["Trade buyer", "Wholesale client", "Export client", "Retail chain"]),
            "taxable_value": taxable, "gst_amount": gst, "invoice_total": total,
            "filing_status": filing,
        })
        seq += 1
    return invoices


def _build_msme(defn: dict[str, Any]) -> tuple[MSME, list[Transaction], list[GSTInvoice]]:
    state_name, state_code = STATES[defn["state_key"]]
    udyam = _udyam(state_code, int(defn["id"].split("-")[1]) * 1000 + RNG.randint(1, 999))
    gstin = _gstin(state_code)
    profile = {
        "city": defn["city"], "state": state_name, "sub_sector": defn["sub_sector"],
        "entity_type": defn["entity_type"], "seasonality": defn["seasonality"],
        "stated_margin_pct": round(defn["margin"] * 100, 1),
        "emi_lakh_monthly": defn["emi_lakh_monthly"],
        "note": defn.get("note", ""),
    }
    m = MSME(
        id=defn["id"], name=defn["name"], sector=defn["sector"],
        sub_sector=defn["sub_sector"], udyam_number=udyam, gstin=gstin,
        city=defn["city"], state=state_name, vintage_years=defn["vintage_years"],
        entity_type=defn["entity_type"], annual_turnover_lakh=defn["annual_turnover_lakh"],
        is_near_miss=int(defn.get("is_near_miss", False)),
        profile_json=dumps(profile),
    )
    tx_data = _generate_transactions(defn)
    inv_data = _generate_invoices(defn, tx_data)
    txns = [Transaction(msme_id=m.id, **t) for t in tx_data]
    invs = [GSTInvoice(msme_id=m.id, **i) for i in inv_data]
    return m, txns, invs


def seed_database(wipe: bool = True) -> dict[str, Any]:
    """Generate + persist all MSMEs. Returns a summary dict."""
    from app.db.database import init_db
    init_db()
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    summary: list[dict[str, Any]] = []
    with session_scope() as s:
        if wipe:
            from app.db.models import AgentOutput, Run
            s.query(AgentOutput).delete()
            s.query(Run).delete()
            s.query(GSTInvoice).delete()
            s.query(Transaction).delete()
            s.query(MSME).delete()
            s.flush()
        for defn in MSME_DEFS:
            m, txns, invs = _build_msme(defn)
            s.add(m)
            s.add_all(txns)
            s.add_all(invs)
            # Also dump JSON seed per MSME
            payload = {
                "msme": {
                    "id": m.id, "name": m.name, "sector": m.sector, "sub_sector": m.sub_sector,
                    "udyam_number": m.udyam_number, "gstin": m.gstin, "city": m.city,
                    "state": m.state, "vintage_years": m.vintage_years, "entity_type": m.entity_type,
                    "annual_turnover_lakh": m.annual_turnover_lakh,
                    "is_near_miss": bool(m.is_near_miss),
                    "profile": json.loads(m.profile_json) if m.profile_json else {},
                },
                "transactions": [t.__dict__ for t in txns if "_sa_instance_state" not in t.__dict__],
                "invoices": [i.__dict__ for i in invs if "_sa_instance_state" not in i.__dict__],
            }
            # Strip SA state keys cleanly:
            payload["transactions"] = [
                {k: v for k, v in t.__dict__.items() if k != "_sa_instance_state"} for t in txns
            ]
            payload["invoices"] = [
                {k: v for k, v in i.__dict__.items() if k != "_sa_instance_state"} for i in invs
            ]
            (SEED_DIR / f"{m.id}.json").write_text(dumps(payload), encoding="utf-8")
            summary.append({"id": m.id, "name": m.name, "sector": m.sector,
                            "transactions": len(txns), "invoices": len(invs),
                            "is_near_miss": bool(m.is_near_miss)})
    return {"msmes": summary, "total_msme": len(summary)}


def is_seeded() -> bool:
    with session_scope() as s:
        return s.scalar(select(MSME).limit(1)) is not None


if __name__ == "__main__":
    out = seed_database()
    print(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"\nSeeded {out['total_msme']} MSMEs into SQLite + JSON seeds at {SEED_DIR}")