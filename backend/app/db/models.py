"""ORM models. JSON fields stored as Text for SQLite/Postgres portability."""
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MSME(Base):
    __tablename__ = "msmes"

    id = Column(String, primary_key=True)  # e.g. "MSME-001"
    name = Column(String, nullable=False)
    sector = Column(String, nullable=False)
    sub_sector = Column(String, default="")
    udyam_number = Column(String, nullable=False)
    gstin = Column(String, nullable=False)
    city = Column(String, default="")
    state = Column(String, default="")
    vintage_years = Column(Float, default=1.0)
    entity_type = Column(String, default="Proprietorship")  # Proprietorship/Partnership/Pvt Ltd
    # Synthesised annual turnover (₹ lakh) — the "stated" figure.
    annual_turnover_lakh = Column(Float, default=0.0)
    # Engineered near-miss inclusion case flag.
    is_near_miss = Column(Integer, default=0)
    profile_json = Column(Text, default="")  # extra profile metadata
    created_at = Column(DateTime, default=_utcnow)

    transactions = relationship("Transaction", back_populates="msme", cascade="all, delete-orphan")
    invoices = relationship("GSTInvoice", back_populates="msme", cascade="all, delete-orphan")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    msme_id = Column(String, ForeignKey("msmes.id"), nullable=False, index=True)
    date = Column(String, nullable=False, index=True)  # ISO yyyy-mm-dd
    description = Column(String, default="")
    category = Column(String, default="other")  # revenue/expense/emi/salary/refund/gst
    amount = Column(Float, nullable=False)  # +credit / -debit
    channel = Column(String, default="UPI")  # UPI/RTGS/NEFT/IMPS/Cheque
    counterparty = Column(String, default="")
    msme = relationship("MSME", back_populates="transactions")


class GSTInvoice(Base):
    __tablename__ = "gst_invoices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    msme_id = Column(String, ForeignKey("msmes.id"), nullable=False, index=True)
    invoice_number = Column(String, nullable=False)
    invoice_date = Column(String, nullable=False)
    party_gstin = Column(String, default="")
    party_name = Column(String, default="")
    taxable_value = Column(Float, default=0.0)
    gst_amount = Column(Float, default=0.0)
    invoice_total = Column(Float, default=0.0)
    filing_status = Column(String, default="filed")  # filed/delayed/missing
    msme = relationship("MSME", back_populates="invoices")


class Run(Base):
    __tablename__ = "runs"

    id = Column(String, primary_key=True)
    msme_id = Column(String, ForeignKey("msmes.id"), nullable=False, index=True)
    status = Column(String, default="pending")  # pending/running/done/failed
    offline = Column(Integer, default=0)
    what_if_json = Column(Text, default="")
    metrics_json = Column(Text, default="")
    report_json = Column(Text, default="")
    events_json = Column(Text, default="")  # full event log for replay
    started_at = Column(DateTime, default=_utcnow)
    finished_at = Column(DateTime, nullable=True)


class AgentOutput(Base):
    __tablename__ = "agent_outputs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, ForeignKey("runs.id"), nullable=False, index=True)
    agent_key = Column(String, nullable=False)
    layer = Column(Integer, default=0)
    output_json = Column(Text, default="")
    status = Column(String, default="done")  # done/failed/fallback
    duration_ms = Column(Integer, default=0)