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


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
