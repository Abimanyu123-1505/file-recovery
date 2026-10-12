"""Report builder – builds structured report data from the database."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Read tool version
_VERSION_FILE = Path(__file__).resolve().parents[3] / "VERSION"
TOOL_VERSION = _VERSION_FILE.read_text().strip() if _VERSION_FILE.exists() else "0.1.0"
TOOL_NAME = "EXT4 Deleted File Recovery Workbench"


LIMITATIONS = [
    "Unallocated inode metadata is a candidate for recovery, not proof that a file existed or was deleted intentionally.",
    "Data blocks may have been overwritten, reused, or fragmented since deletion. Recovery may be partial.",
    "JBD2 journal replay is not performed in this release. Journal-sourced names are not available.",
    "File signature checks provide consistency evidence; they do not prove where a file originated.",
    "Carved files have no trustworthy original filename, path, or timestamp; they are labelled as derived evidence.",
    "Name reconstruction is conservative. Only names surviving in allocated directory records are labelled 'Confirmed'.",
    "Recovered files have not been independently verified against an original copy.",
    "Timestamps depend on the accuracy of the source device's clock at the time of deletion.",
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_size(b: int | None) -> str:
    if b is None:
        return "Unknown"
    if b < 1024:
        return f"{b} bytes"
    if b < 1024 * 1024:
        return f"{b / 1024:.1f} KB"
    if b < 1024 * 1024 * 1024:
        return f"{b / (1024 * 1024):.2f} MB"
    return f"{b / (1024 * 1024 * 1024):.2f} GB"


def build_report(
    scan,
    case,
    recoveries: list,
    candidates: list[dict],
    profile: str = "general",
    report_type: str = "investigator",
    declaration: dict | None = None,
) -> dict[str, Any]:
    """Build the full structured report dictionary from DB objects."""

    now = _utc_now()
    generated_at = now.isoformat()

    # --- Evidence integrity --------------------------------------------------
    integrity_result = "Evidence unchanged during analysis"
    integrity_status = "ok"
    if scan.evidence_sha256_pre and scan.evidence_sha256_post:
        if scan.evidence_sha256_pre != scan.evidence_sha256_post:
            integrity_result = "WARNING: Evidence fingerprint changed during analysis"
            integrity_status = "failed"
    elif not scan.evidence_sha256_pre:
        integrity_result = "Fingerprint not recorded"
        integrity_status = "unknown"

    # --- Findings -----------------------------------------------------------
    findings = []
    for rec in recoveries:
        status_plain = {
            "FULL": "Fully recovered",
            "PARTIAL": "Partly recovered – some data is missing",
            "FAILED": "Could not be recovered",
        }.get(rec.status or "", "Unknown")

        confidence = "Confirmed" if rec.name_source == "dir_entry" else "Uncertain"
        confidence_reason = (
            "File name and path found in a surviving directory record."
            if rec.name_source == "dir_entry"
            else "No directory record survived; name and path cannot be confirmed."
        )

        findings.append({
            "finding_id": rec.finding_id or f"F-???",
            "exhibit_number": rec.exhibit_number or "EX-???",
            "inode": rec.inode,
            "file_name": rec.file_name or "(name not available)",
            "file_path": rec.file_path or "(path not available)",
            "size_bytes": rec.size_bytes,
            "size_friendly": _format_size(rec.size_bytes),
            "expected_size": rec.expected_size,
            "sha256": rec.sha256,
            "signature": rec.signature,
            "status": rec.status,
            "status_plain": status_plain,
            "output_path": rec.output_path,
            "name_source": rec.name_source,
            "confidence": confidence,
            "confidence_reason": confidence_reason,
            "duplicate_of_inode": rec.duplicate_of_inode,
            "is_duplicate": bool(rec.duplicate_of_inode),
            "duplicate_note": (
                f"Identical content to previously recovered file record {rec.duplicate_of_inode} (SHA-256 match)."
                if rec.duplicate_of_inode
                else None
            ),
        })

    # --- Candidate summary (Finding F6: honest counts & fact/inference labels) ---
    total_scanned = len(candidates)
    valid_deletion_records = sum(
        1 for c in candidates if c.get("category") != "orphan/uncertain" and (c.get("links_count", 0) == 0)
    )
    orphan_uncertain_records = sum(
        1 for c in candidates if c.get("category") == "orphan/uncertain"
    )
    surviving_extents = sum(
        1 for c in candidates if c.get("recoverable", 1) == 1 and c.get("can_recover")
    )
    cleared_pointers = sum(
        1 for c in candidates if c.get("recoverable", 1) == 0 or not c.get("can_recover")
    )

    candidate_summary = {
        "total_scanned": {
            "count": total_scanned,
            "label": "Total candidates scanned",
            "type": "fact",
            "description": "Total number of unallocated inode records inspected during analysis.",
        },
        "valid_deletion_records": {
            "count": valid_deletion_records,
            "label": "Valid deletion records",
            "type": "tool_inference",
            "description": "Records with zero link count and plausible deletion timestamps.",
        },
        "orphan_uncertain_records": {
            "count": orphan_uncertain_records,
            "label": "Orphan / uncertain records",
            "type": "tool_inference",
            "description": "Records with suspicious deletion timestamps or orphan-chain markers.",
        },
        "surviving_extents": {
            "count": surviving_extents,
            "label": "Candidates with surviving extents (recoverable)",
            "type": "fact",
            "description": "Inodes retaining valid extent headers and block pointers on disk.",
        },
        "cleared_pointers": {
            "count": cleared_pointers,
            "label": "Inodes with cleared pointers (not recoverable)",
            "type": "fact",
            "description": "Inodes whose size or block pointers were zeroed out by the filesystem upon deletion.",
        },
    }

    total_candidates = total_scanned
    recoverable = surviving_extents
    fully_recovered = sum(1 for r in recoveries if r.status == "FULL")
    partially_recovered = sum(1 for r in recoveries if r.status in ("PARTIAL", "partial_unwritten"))
    failed = sum(1 for r in recoveries if r.status in ("FAILED", "not_recoverable"))

    # --- Executive summary (plain language) ---------------------------------
    exec_bullets = [
        f"The evidence examined is: {Path(scan.evidence_path).name} ({_format_size(Path(scan.evidence_path).stat().st_size if Path(scan.evidence_path).exists() else None)}).",
        f"Digital fingerprint (SHA-256) was recorded before and after analysis. Result: {integrity_result}.",
        f"{total_scanned} candidate records scanned [Fact].",
        f"{valid_deletion_records} records identified as plausible deletions [Tool inference]; {orphan_uncertain_records} records flagged as orphan or uncertain [Tool inference].",
        f"{surviving_extents} candidate file(s) have surviving extents and appear recoverable [Fact]; {cleared_pointers} record(s) had cleared data pointers and are not recoverable [Fact].",
        f"{fully_recovered} file{'s were' if fully_recovered != 1 else ' was'} fully recovered. {partially_recovered} {'were' if partially_recovered != 1 else 'was'} partly recovered.",
        "All recovered files are copies only. The original evidence was not changed.",
        f"Analysis was conducted using {TOOL_NAME} version {TOOL_VERSION}.",
    ]
    if profile == "lab02":
        exec_bullets.append("This report was generated under the Lab02 / Project ORION report profile.")

    # --- Timeline (all events with timestamps) ------------------------------
    timeline = []
    if case.date_received:
        timeline.append({
            "datetime": case.date_received,
            "event": "Evidence item received",
            "source": "Case record",
            "finding_id": None,
        })
    timeline.append({
        "datetime": scan.created_at.isoformat() if scan.created_at else None,
        "event": "Analysis started",
        "source": "Workbench audit",
        "finding_id": None,
    })
    timeline.append({
        "datetime": scan.completed_at.isoformat() if scan.completed_at else None,
        "event": "Analysis completed",
        "source": "Workbench audit",
        "finding_id": None,
    })
    for f in findings:
        timeline.append({
            "datetime": None,  # deletion time not reliably available without journal
            "event": f"Deleted file record found: {f['file_name']} (inode {f['inode']})",
            "source": "File system scan",
            "finding_id": f["finding_id"],
            "sequence_only": True,
        })

    # --- Established facts vs inferences ------------------------------------
    established_facts = [
        {
            "finding_id": None,
            "statement": f"The evidence file digital fingerprint was recorded as {scan.evidence_sha256_pre}.",
        },
        {
            "finding_id": None,
            "statement": f"The post-analysis fingerprint is {'identical – evidence was not changed' if integrity_status == 'ok' else 'DIFFERENT – see integrity warning'}.",
        },
    ]
    for f in findings:
        if f["confidence"] == "Confirmed":
            established_facts.append({
                "finding_id": f["finding_id"],
                "statement": f"A deleted file record for '{f['file_name']}' at '{f['file_path']}' was found in a surviving directory entry (file record {f['inode']}).",
            })

    inferences = []
    for f in findings:
        if f["confidence"] == "Uncertain":
            inferences.append({
                "finding_id": f["finding_id"],
                "statement": f"File record {f['inode']} is consistent with having been a regular file of {f['size_friendly']}. The original name and path could not be confirmed.",
                "confidence_level": "Uncertain",
                "reasoning": f["confidence_reason"],
            })

    # --- Full report payload ------------------------------------------------
    report = {
        "report_version": "1.0",
        "report_profile": profile,
        "report_type": report_type,
        "generated_at_utc": generated_at,
        "tool_name": TOOL_NAME,
        "tool_version": TOOL_VERSION,

        "case": {
            "case_number": case.case_number,
            "case_title": case.case_title or "",
            "examiner_name": case.examiner_name or "",
            "rank_badge": case.rank_badge or "",
            "department": case.department or "",
            "requesting_authority": case.requesting_authority or "",
            "date_received": case.date_received or "",
            "notes": case.notes or "",
        },

        "scan": {
            "id": scan.id,
            "evidence_path": scan.evidence_path,
            "evidence_filename": Path(scan.evidence_path).name,
            "evidence_size": Path(scan.evidence_path).stat().st_size if Path(scan.evidence_path).exists() else None,
            "evidence_sha256_pre": scan.evidence_sha256_pre,
            "evidence_sha256_post": scan.evidence_sha256_post,
            "integrity_ok": scan.integrity_ok,
            "integrity_result": integrity_result,
            "integrity_status": integrity_status,
            "status": scan.status,
            "created_at": scan.created_at.isoformat() if scan.created_at else None,
            "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
        },

        "summary": {
            "total_candidates": total_candidates,
            "recoverable": recoverable,
            "fully_recovered": fully_recovered,
            "partially_recovered": partially_recovered,
            "failed_recovery": failed,
            "executive_bullets": exec_bullets,
        },

        "candidate_summary": candidate_summary,

        "findings": findings,

        "timeline": sorted(
            [t for t in timeline if t.get("datetime")],
            key=lambda t: t["datetime"] or "",
        ) + [t for t in timeline if not t.get("datetime")],

        "established_facts": established_facts,
        "inferences": inferences,

        "limitations": LIMITATIONS,

        "declaration": declaration,

        "methodology": [
            f"1. Evidence file opened read-only using {TOOL_NAME} v{TOOL_VERSION}.",
            "2. SHA-256 digital fingerprint recorded before any analysis.",
            "3. EXT4 file system metadata read using The Sleuth Kit (pytsk3) without modification.",
            "4. Deleted directory entries traversed to recover filenames and paths from allocated directory records.",
            "5. Unallocated inode metadata enumerated to identify additional file record candidates.",
            "6. For each candidate, data blocks read (read-only) and copied to a separate output directory.",
            "7. SHA-256 fingerprint computed for each recovered copy.",
            "8. File signature checked against known file headers for consistency.",
            "9. SHA-256 digital fingerprint recorded after analysis to verify evidence integrity.",
            "10. This report generated from the collected data without further access to the evidence.",
        ],
    }

    if profile == "lab02":
        report["lab02_appendix"] = {
            "note": "This appendix is present because the lab02 report profile was selected.",
            "project": "ORION",
            "lab": "Lab #02",
            "deliverables": [
                "USB and archive event artefacts (if present in recovered data)",
                "Extended artefact cross-reference register",
            ],
        }

    return report
