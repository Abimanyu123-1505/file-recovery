"""Background scan worker – runs the forensic pipeline and updates the DB."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Allow importing the existing ext4recover library
_repo_root = Path(__file__).resolve().parents[3]
_src = _repo_root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from sqlalchemy.orm import Session

from ..database import Recovery, Scan, SessionLocal, record_audit

# ---------------------------------------------------------------------------
# Stage mapping: internal stage names → plain-language phase labels
# ---------------------------------------------------------------------------
STAGES = [
    ("checking",   "Checking the evidence copy",       1, 4),
    ("reading_fs", "Reading the file system",           2, 4),
    ("searching",  "Looking for deleted files",         3, 4),
    ("integrity",  "Final integrity check",             4, 4),
]

_SCAN_CANCELLED: dict[int, bool] = {}


def cancel_scan(scan_id: int) -> None:
    _SCAN_CANCELLED[scan_id] = True
    try:
        db = SessionLocal()
        record_audit(db, "scan_cancel", target=str(scan_id), details=f"Scan {scan_id} cancellation requested")
        db.close()
    except Exception:
        pass


def _db() -> Session:
    return SessionLocal()


def _update_stage(scan_id: int, stage_key: str, db: Session) -> None:
    for key, label, idx, total in STAGES:
        if key == stage_key:
            scan = db.get(Scan, scan_id)
            if scan:
                scan.stage = label
                scan.stage_index = idx
                scan.stage_total = total
                db.commit()
            return


def _set_status(scan_id: int, status: str, db: Session, error: str | None = None) -> None:
    scan = db.get(Scan, scan_id)
    if scan:
        scan.status = status
        if error:
            scan.error_message = error
        if status in ("complete", "failed", "cancelled"):
            scan.completed_at = datetime.now(timezone.utc)
        db.commit()


# ---------------------------------------------------------------------------
# File-type helpers
# ---------------------------------------------------------------------------
_TYPE_MAP = {
    "1": "Regular file",
    "2": "Directory",
    "3": "Character device",
    "4": "Block device",
    "5": "FIFO",
    "6": "Socket",
    "7": "Symbolic link",
    "TSK_FS_META_TYPE_REG": "Regular file",
    "TSK_FS_META_TYPE_DIR": "Directory",
    "TSK_FS_META_TYPE_LNK": "Symbolic link",
}

_EXT_TYPE = {
    ".pdf": "PDF document",
    ".doc": "Word document",
    ".docx": "Word document",
    ".xls": "Spreadsheet",
    ".xlsx": "Spreadsheet",
    ".ppt": "Presentation",
    ".pptx": "Presentation",
    ".txt": "Text file",
    ".jpg": "Image (JPEG)",
    ".jpeg": "Image (JPEG)",
    ".png": "Image (PNG)",
    ".zip": "ZIP archive",
    ".gz": "Compressed archive",
    ".tar": "Archive",
    ".mp4": "Video",
    ".mp3": "Audio",
    ".csv": "Spreadsheet (CSV)",
    ".json": "JSON data file",
    ".xml": "XML data file",
    ".html": "Web page",
    ".py": "Python script",
    ".db": "Database file",
    ".sqlite": "Database file",
    ".exe": "Windows executable",
    ".dll": "Windows library",
}


def _friendly_type(file_type: str, name: str | None) -> str:
    if name:
        ext = Path(name).suffix.lower()
        if ext in _EXT_TYPE:
            return _EXT_TYPE[ext]
    return _TYPE_MAP.get(file_type, "Unknown file type")


def _name_source(candidate: Any) -> str:
    """Determine how the name was found."""
    if getattr(candidate, "path", None) or getattr(candidate, "name", None):
        return "dir_entry"
    return "none"


# ---------------------------------------------------------------------------
# Main async scan task
# ---------------------------------------------------------------------------
async def run_scan(scan_id: int, evidence_path: str, case_output_dir: str) -> None:
    """Run the full forensic pipeline in a thread; update DB at each stage."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_scan_sync, scan_id, evidence_path, case_output_dir)


def _run_scan_sync(scan_id: int, evidence_path: str, case_output_dir: str) -> None:
    db = _db()
    try:
        _set_status(scan_id, "running", db)

        # ── Stage 1: Hash pre-analysis ──────────────────────────────────────
        _update_stage(scan_id, "checking", db)
        if _SCAN_CANCELLED.get(scan_id):
            _set_status(scan_id, "cancelled", db)
            return

        try:
            from ext4recover.hashing import sha256_file
            from ext4recover.evidence import open_evidence, EvidenceError
        except ImportError:
            _set_status(scan_id, "failed", db, "Core forensic library not found. Is ext4recover installed?")
            return

        try:
            evidence = open_evidence(evidence_path, output_dir=case_output_dir)
        except Exception as exc:
            _set_status(scan_id, "failed", db, f"Could not open evidence file: {exc}")
            return

        # Finding I3: Audit ledger scan start record
        try:
            record_audit(db, "scan_start", target=evidence_path, details=f"Scan {scan_id} started")
        except Exception as exc:
            _set_status(scan_id, "failed", db, f"Audit ledger write failed: {exc}")
            return

        # Finding I1: Chunked hashing with cancellation checks
        try:
            pre_hash = sha256_file(
                evidence_path,
                chunk_size=1024 * 1024,
                check_cancelled=lambda: bool(_SCAN_CANCELLED.get(scan_id)),
            )
        except RuntimeError:
            _set_status(scan_id, "cancelled", db)
            return

        scan = db.get(Scan, scan_id)
        if scan:
            scan.evidence_sha256_pre = pre_hash
            db.commit()

        if _SCAN_CANCELLED.get(scan_id):
            _set_status(scan_id, "cancelled", db)
            return

        # ── Stage 2: Open filesystem & discover partitions ──────────────────
        _update_stage(scan_id, "reading_fs", db)

        try:
            from ext4recover.tsk import open_fs, deleted_candidates, deleted_directory_entries
            from ext4recover.partitions import find_filesystem_offsets
            from ext4recover.ext4 import inspect_superblock

            stream = evidence.analysis_path if not evidence.direct_ewf else None
            if stream is None:
                _set_status(scan_id, "failed", db, "E01/EWF requires ewfmount and --stream support via the CLI.")
                return

            offsets = find_filesystem_offsets(stream)
        except Exception as exc:
            _set_status(scan_id, "failed", db, f"Could not inspect evidence partitions: {exc}")
            return

        if _SCAN_CANCELLED.get(scan_id):
            _set_status(scan_id, "cancelled", db)
            return

        # ── Stage 3: Find deleted files across partitions ────────────────────
        _update_stage(scan_id, "searching", db)

        all_candidates: list[dict] = []
        fs_limitations: list[str] = []

        for fs_off in offsets:
            try:
                sb_info = inspect_superblock(stream, fs_off)
                fs_label = sb_info.get("filesystem", "EXT4")
                unsupported = sb_info.get("unsupported_incompat_features", [])
                if unsupported:
                    fs_limitations.append(
                        f"Partition at offset {fs_off} uses unsupported features: {', '.join(unsupported)}."
                    )

                fs = open_fs(stream, fs_off, ewf=evidence.direct_ewf)
                named_entries = deleted_directory_entries(fs, limit=200)
                inode_candidates = deleted_candidates(fs, limit=200)
                known_inodes = {c.inode for c in named_entries}
                merged = named_entries + [c for c in inode_candidates if c.inode not in known_inodes]

                for candidate in merged:
                    src = _name_source(candidate)
                    if src == "dir_entry":
                        name_confidence = "confirmed"
                        name_confidence_label = "Name confirmed"
                        name_confidence_note = "The file name was found in a surviving directory record."
                    else:
                        name_confidence = "uncertain"
                        name_confidence_label = "Original name not available"
                        name_confidence_note = "No directory record survived. The original name cannot be determined."

                    can_recover = bool(candidate.size and candidate.size > 0)
                    recoverable = 1 if can_recover else 0
                    not_recoverable_reason = None if can_recover else "inode size and data pointers were cleared by the filesystem"

                    all_candidates.append({
                        "inode": candidate.inode,
                        "fs_offset": fs_off,
                        "filesystem": fs_label,
                        "category": "deleted",
                        "size": candidate.size,
                        "allocated": candidate.allocated,
                        "file_type": candidate.file_type,
                        "friendly_type": _friendly_type(candidate.file_type, getattr(candidate, "name", None)),
                        "name": getattr(candidate, "name", None),
                        "path": getattr(candidate, "path", None),
                        "name_source": src,
                        "name_confidence": name_confidence,
                        "name_confidence_label": name_confidence_label,
                        "name_confidence_note": name_confidence_note,
                        "can_recover": can_recover,
                        "recoverable": recoverable,
                        "not_recoverable_reason": not_recoverable_reason,
                    })
            except Exception:
                continue

        if _SCAN_CANCELLED.get(scan_id):
            _set_status(scan_id, "cancelled", db)
            return

        # ── Stage 4: Post-hash integrity check ───────────────────────────────
        _update_stage(scan_id, "integrity", db)

        try:
            post_hash = sha256_file(
                evidence_path,
                chunk_size=1024 * 1024,
                check_cancelled=lambda: bool(_SCAN_CANCELLED.get(scan_id)),
            )
        except RuntimeError:
            _set_status(scan_id, "cancelled", db)
            return
        integrity_ok = pre_hash == post_hash

        candidates = all_candidates[:200]

        scan = db.get(Scan, scan_id)
        if scan:
            scan.evidence_sha256_post = post_hash
            scan.integrity_ok = integrity_ok
            scan.candidates_json = json.dumps(candidates)
            db.commit()

        _set_status(scan_id, "complete", db)

    except Exception as exc:
        try:
            _set_status(scan_id, "failed", db, f"Unexpected error: {exc}")
        except Exception:
            pass
    finally:
        db.close()
        _SCAN_CANCELLED.pop(scan_id, None)
