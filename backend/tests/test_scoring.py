"""Unit tests for the deterministic scoring moat — prevents on-stage NaN/wrong math."""
from app.scoring.metrics import compute_metrics


def _txns():
    """A simple, known-shape 12-month ledger."""
    txns = []
    # Monthly: 1,00,000 revenue, 70,000 opex, 15,000 EMI, 9,000 GST -> net +6,000
    for m in range(1, 13):
        txns.append({"date": f"2025-{m:02d}-03", "category": "revenue", "amount": 100000})
        txns.append({"date": f"2025-{m:02d}-08", "category": "expense", "amount": -70000})
        txns.append({"date": f"2025-{m:02d}-05", "category": "emi", "amount": -15000})
        txns.append({"date": f"2025-{m:02d}-20", "category": "gst", "amount": -9000})
        txns.append({"date": f"2025-{m:02d}-01", "category": "salary", "amount": -20000})
    return txns


def _msme():
    return {"id": "T1", "sector": "Manufacturing", "vintage_years": 5.0,
            "annual_turnover_lakh": 120.0, "is_near_miss": False,
            "profile": {"seasonality": "flat"}}


def _invoices():
    return [{"filing_status": "filed"} for _ in range(20)]


def test_basic_shapes():
    m = compute_metrics(_msme(), _txns(), _invoices())
    assert m["data_months"] == 12
    assert m["avg_monthly_revenue"] == 100000
    # EMI burden = 15000 / 100000 = 0.15
    assert abs(m["emi_burden_ratio"] - 0.15) < 0.01
    # flat seasonality -> index ~0
    assert m["seasonality_index"] < 0.05
    assert 0 <= m["health_score"] <= 100
    assert 0 <= m["loan_readiness"] <= 100
    assert m["dscr"] > 0


def test_gst_consistency():
    m = compute_metrics(_msme(), _txns(), [{"filing_status": "filed"}] * 16 +
                        [{"filing_status": "delayed"}] * 3 + [{"filing_status": "missing"}] * 1)
    assert abs(m["gst_consistency"] - 0.8) < 0.01
    assert m["gst_delayed"] == 3 and m["gst_missing"] == 1


def test_emi_burden_high_triggers_signal():
    txns = []
    for m_ in range(1, 13):
        txns.append({"date": f"2025-{m_:02d}-03", "category": "revenue", "amount": 100000})
        txns.append({"date": f"2025-{m_:02d}-05", "category": "emi", "amount": -45000})  # 45% burden
        txns.append({"date": f"2025-{m_:02d}-08", "category": "expense", "amount": -40000})
    m = compute_metrics(_msme(), txns, _invoices())
    assert m["emi_burden_ratio"] > 0.40
    sig = [s for s in m["early_warning_signals"] if s["source_metric"] == "emi_burden_ratio"]
    assert sig and sig[0]["severity"] == "high"


def test_stress_probability_bounded_and_monotone_ish():
    m = compute_metrics(_msme(), _txns(), _invoices())
    sp = m["stress_probabilities"]
    for k in ("30d", "60d", "90d"):
        assert 0.0 <= sp[k] <= 1.0
    # longer horizon should be >= shorter for healthy-ish firm (no stricter drop)
    assert sp["90d"] >= sp["30d"] - 0.05


def test_what_if_revenue_delta_lowers_buffer():
    base = compute_metrics(_msme(), _txns(), _invoices())
    down = compute_metrics(_msme(), _txns(), _invoices(), revenue_delta=-0.20)
    # 20% revenue drop should not increase projected min balance
    assert down["projection_min_balance"] <= base["projection_min_balance"]
    assert down["revenue_delta"] == -0.20


def test_no_data_does_not_crash():
    m = compute_metrics(_msme(), [], [])
    assert m["health_score"] == 0
    assert m["early_warning_signals"] == [] or m["data_months"] == 0


def test_near_miss_inclusion_flag():
    # Use the real seeded near-miss shape: thin margins + a stressed stretch.
    from app.db.seed import _build_msme, MSME_DEFS
    defn = next(d for d in MSME_DEFS if d["is_near_miss"])
    msme_obj, txns_obj, invs_obj = _build_msme(defn)
    msme = {"id": msme_obj.id, "sector": msme_obj.sector, "vintage_years": msme_obj.vintage_years,
            "annual_turnover_lakh": msme_obj.annual_turnover_lakh, "is_near_miss": True,
            "profile": {"seasonality": msme_obj.profile_json and __import__("json").loads(msme_obj.profile_json).get("seasonality", "flat")}}
    txns = [{k: v for k, v in t.__dict__.items() if k != "_sa_instance_state"} for t in txns_obj]
    invs = [{k: v for k, v in i.__dict__.items() if k != "_sa_instance_state"} for i in invs_obj]
    m = compute_metrics(msme, txns, invs)
    # The near-miss firm should have either a stress signal or low buffer but still compute.
    assert m["data_months"] > 0
    assert m["health_score"] >= 0