from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class XBRLFact(Base):
    __tablename__ = "xbrl_facts"

    id: Mapped[int] = mapped_column(primary_key=True)
    company: Mapped[str] = mapped_column(String)
    canonical_concept: Mapped[str] = mapped_column(String)
    raw_tag: Mapped[str] = mapped_column(String)
    value: Mapped[float] = mapped_column(Numeric)
    unit: Mapped[str] = mapped_column(String)
    form: Mapped[str] = mapped_column(String)
    fiscal_year: Mapped[int] = mapped_column()
    fiscal_period: Mapped[str] = mapped_column(String)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    accession_number: Mapped[str] = mapped_column(String)
    filed_date: Mapped[date] = mapped_column(Date)
    gaap_basis: Mapped[str] = mapped_column(String)

class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(primary_key=True)
    company: Mapped[str] = mapped_column(String)
    claim_quote: Mapped[str] = mapped_column(Text)
    metric: Mapped[str] = mapped_column(String)
    value_low: Mapped[float] = mapped_column(Numeric, nullable=True)
    value_high: Mapped[float] = mapped_column(Numeric, nullable=True)
    comparison_basis: Mapped[str] = mapped_column(String, nullable=True)
    period: Mapped[str] = mapped_column(String, nullable=True)
    source_span: Mapped[str] = mapped_column(String, nullable=True)
    extraction_confidence: Mapped[float] = mapped_column(nullable=True)

class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_url: Mapped[str] = mapped_column(String)
    filing_accession: Mapped[str] = mapped_column(String)
    source_section: Mapped[str] = mapped_column(String, nullable=True)
    char_range: Mapped[str] = mapped_column(String, nullable=True)
    table_cell_ref: Mapped[str] = mapped_column(String, nullable=True)

class Verification(Base):
    __tablename__ = "verifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"))
    fact_id: Mapped[int] = mapped_column(ForeignKey("xbrl_facts.id"), nullable=True)
    citation_id: Mapped[int] = mapped_column(ForeignKey("citations.id"), nullable=True)
    normalization_rules_applied: Mapped[str] = mapped_column(String, nullable=True)
    verdict: Mapped[str] = mapped_column(String)
    difference: Mapped[float] = mapped_column(Numeric, nullable=True)
    abstention_reason: Mapped[str] = mapped_column(String, nullable=True)

class GuidanceOutcome(Base):
    __tablename__ = "guidance_outcomes"

    id: Mapped[int] = mapped_column(primary_key=True)
    company: Mapped[str] = mapped_column(String)
    guided_period: Mapped[str] = mapped_column(String)
    guided_metric: Mapped[str] = mapped_column(String)
    guided_low: Mapped[float] = mapped_column(Numeric, nullable=True)
    guided_high: Mapped[float] = mapped_column(Numeric, nullable=True)
    tolerance: Mapped[float] = mapped_column(Numeric, nullable=True)
    reported_value: Mapped[float] = mapped_column(Numeric, nullable=True)
    outcome: Mapped[str] = mapped_column(String, nullable=True)
    confidence: Mapped[float] = mapped_column(nullable=True)

class EvalLabel(Base):
    __tablename__ = "eval_labels"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column()
    label_type: Mapped[str] = mapped_column(String)
    human_label: Mapped[str] = mapped_column(String)
    rationale: Mapped[str] = mapped_column(Text, nullable=True)
    annotator: Mapped[str] = mapped_column(String, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)