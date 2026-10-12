"""Pydantic schemas for request/response validation."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class CaseCreate(BaseModel):
    case_number: str = Field(..., min_length=1)
    case_title: Optional[str] = None
    examiner_name: Optional[str] = None
    rank_badge: Optional[str] = None
    department: Optional[str] = None
    requesting_authority: Optional[str] = None
    date_received: Optional[str] = None
    notes: Optional[str] = None


class CaseOut(CaseCreate):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ScanRequest(BaseModel):
    case_id: int
    evidence_path: str
    report_profile: str = "general"  # "general" | "lab02"


class ScanOut(BaseModel):
    id: int
    case_id: int
    evidence_path: str
    status: str
    stage: Optional[str] = None
    stage_index: int = 0
    stage_total: int = 4
    error_message: Optional[str] = None
    evidence_sha256_pre: Optional[str] = None
    evidence_sha256_post: Optional[str] = None
    integrity_ok: Optional[bool] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CandidateOut(BaseModel):
    inode: int
    size: int
    allocated: bool
    file_type: str
    name: Optional[str] = None
    path: Optional[str] = None
    name_source: str = "none"  # dir_entry / slack / none


class RecoverRequest(BaseModel):
    scan_id: int
    inodes: list[int]
    output_dir: Optional[str] = None


class RecoveryOut(BaseModel):
    id: int
    scan_id: int
    inode: int
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    size_bytes: Optional[int] = None
    expected_size: Optional[int] = None
    sha256: Optional[str] = None
    signature: Optional[str] = None
    status: Optional[str] = None
    output_path: Optional[str] = None
    name_source: Optional[str] = None
    duplicate_of_inode: Optional[int] = None
    exhibit_number: Optional[str] = None
    finding_id: Optional[str] = None

    model_config = {"from_attributes": True}


class EvidenceCheckOut(BaseModel):
    path: str
    exists: bool
    is_file: bool
    size: Optional[int] = None
    readable: bool
    looks_like_ext4: bool
    friendly_description: str
    error: Optional[str] = None


class EvidenceListOut(BaseModel):
    files: list[dict[str, Any]]


class ExaminerDeclaration(BaseModel):
    name: str
    rank: str
    date: str
    statement: str = "I confirm the contents are accurate to the best of my knowledge"


class ReportRequest(BaseModel):
    scan_id: int
    profile: str = "general"  # "general" | "lab02"
    report_type: str = "investigator"  # "investigator" | "forensic"
    declaration: Optional[ExaminerDeclaration] = None
