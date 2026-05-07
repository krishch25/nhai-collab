"""SQLAlchemy models for raw data, taxonomy rules, classifications, and audit tables."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ProcessingJob(Base):
    """
    Tracks each background job (training, inference, synthesis).
    """

    __tablename__ = "processing_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)  # "TRAINING" | "INFERENCE" | "SYNTHESIS"
    status: Mapped[str] = mapped_column(String(32), default="PENDING")  # PENDING | PROCESSING | COMPLETED | FAILED
    total_rows: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    processed_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_log: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class SystemMetric(Base):
    """
    Tracks code changes, model configuration logs, and system analytics.
    """
    __tablename__ = "system_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class RawData(Base):
    """
    Stores each ingested raw-material row from Excel (row-wise).
    Columns: ID, batch_id, file_id (via file_name or batch), row index, raw_text, structured payload, timestamps.
    """

    __tablename__ = "raw_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    batch_id: Mapped[str] = mapped_column(String(64), index=True)
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    row_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Primary text for lookups and semantic matching (e.g. material description or concatenated key fields)
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    # Structured fields (material_code, description, etc.) for rule matching
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    classifications: Mapped[list["ClassifiedOutput"]] = relationship(
        back_populates="raw_data",
        cascade="all, delete-orphan",
    )

    __table_args__ = (Index("ix_raw_data_batch_row", "batch_id", "row_index"),)


class TaxonomyRule(Base):
    """
    Stores explicit IF/THEN rules crafted by Agent 0.
    Columns: ID, rule name, condition expression/JSON, l0/l1/l2, provenance, confidence, active flag, etc.
    """

    __tablename__ = "taxonomy_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Human-readable IF condition and structured JSON for evaluation
    condition_expression: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    condition_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # THEN: target taxonomy labels
    l0: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    l1: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    l2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Provenance (who/when created)
    source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # agent | human
    created_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    classifications: Mapped[list["ClassifiedOutput"]] = relationship(
        back_populates="rule",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_taxonomy_rules_active", "is_active"),
        Index("ix_taxonomy_rules_l0_l1_l2", "l0", "l1", "l2"),
    )


class ClassifiedOutput(Base):
    """
    Stores final classification results for each raw material.
    Columns: ID, FK to RawData, l0/l1/l2, confidence, rule_id or vector_match_id, status, timestamps.
    """

    __tablename__ = "classified_output"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    raw_data_id: Mapped[int] = mapped_column(
        ForeignKey("raw_data.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("taxonomy_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    l0: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    l1: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    l2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # If classification came from ChromaDB semantic match, store neighbor ID
    vector_match_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Status: pending | confirmed | rejected | review
    status: Mapped[str] = mapped_column(String(32), default="confirmed", nullable=False)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    raw_data: Mapped["RawData"] = relationship(back_populates="classifications")
    rule: Mapped[Optional["TaxonomyRule"]] = relationship(
        back_populates="classifications"
    )

    __table_args__ = (
        Index("ix_classified_output_status", "status"),
        Index("ix_classified_output_raw_rule", "raw_data_id", "rule_id"),
    )


class RuleAudit(Base):
    """
    Audit trail for taxonomy rule changes (create, update, deactivate).
    Helper table for governance and continuous learning tracking.
    """

    __tablename__ = "rule_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    rule_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)  # created | updated | deactivated
    old_values: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    new_values: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    performed_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
