"""Database configuration and models."""

import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

DB_PATH = Path(os.environ.get("DB_PATH", "workbench.db"))
EVIDENCE_DIR = os.environ.get("EVIDENCE_DIR", "")

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    case_number = Column(String(120), nullable=False, index=True)
    case_title = Column(String(255), nullable=True)
    examiner_name = Column(String(255), nullable=True)
    rank_badge = Column(String(120), nullable=True)
    department = Column(String(255), nullable=True)
    requesting_authority = Column(String(255), nullable=True)
    date_received = Column(String(50), nullable=True)  # ISO date string
    notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    scans = relationship("Scan", back_populates="case", cascade="all, delete-orphan")


class Scan(Base):
    __tablename__ = "scans"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    evidence_path = Column(String(2048), nullable=False)
    evidence_sha256_pre = Column(String(64), nullable=True)
    evidence_sha256_post = Column(String(64), nullable=True)
    integrity_ok = Column(Boolean, nullable=True)
    status = Column(String(32), default="pending")  # pending/running/complete/failed/cancelled
    stage = Column(String(64), nullable=True)
    stage_index = Column(Integer, default=0)
    stage_total = Column(Integer, default=4)
    error_message = Column(Text, nullable=True)
    candidates_json = Column(Text, nullable=True)  # JSON array of candidates
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    case = relationship("Case", back_populates="scans")
    recoveries = relationship(
        "Recovery", back_populates="scan", cascade="all, delete-orphan"
    )


class Recovery(Base):
    __tablename__ = "recoveries"

    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scans.id"), nullable=False)
    inode = Column(Integer, nullable=False)
    file_name = Column(String(512), nullable=True)
    file_path = Column(String(2048), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    expected_size = Column(Integer, nullable=True)
    sha256 = Column(String(64), nullable=True)
    signature = Column(String(64), nullable=True)
    status = Column(String(32), nullable=True)  # FULL / PARTIAL / FAILED
    output_path = Column(String(2048), nullable=True)
    name_source = Column(String(32), nullable=True)  # dir_entry / slack / none
    duplicate_of_inode = Column(Integer, nullable=True)
    exhibit_number = Column(String(16), nullable=True)
    finding_id = Column(String(16), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    scan = relationship("Scan", back_populates="recoveries")


class AuditEntry(Base):
    __tablename__ = "audit_ledger"

    id = Column(Integer, primary_key=True, index=True)
    examiner_id = Column(String(255), nullable=True)
    timestamp = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    action = Column(String(64), nullable=False)
    target = Column(String(1024), nullable=True)
    input_hash = Column(String(64), nullable=True)
    output_hash = Column(String(64), nullable=True)
    details = Column(Text, nullable=True)


def record_audit(
    db: Session,
    action: str,
    examiner_id: str | None = None,
    target: str | None = None,
    input_hash: str | None = None,
    output_hash: str | None = None,
    details: str | None = None,
) -> AuditEntry:
    """Write an immutable, append-only record to the audit ledger (Finding I3).
    
    If the ledger write fails, the action MUST fail (fail-closed).
    """
    try:
        entry = AuditEntry(
            examiner_id=examiner_id,
            timestamp=datetime.now(timezone.utc),
            action=action,
            target=target,
            input_hash=input_hash,
            output_hash=output_hash,
            details=details,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry
    except Exception as exc:
        db.rollback()
        raise RuntimeError(f"Fail-closed: Audit ledger write failed for action '{action}': {exc}") from exc


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
