"""Recovery service – writes derived copies of deleted files, never touches evidence."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_repo_root = Path(__file__).resolve().parents[4]
_src = _repo_root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from sqlalchemy.orm import Session

from ..database import Recovery, Scan


def _make_exhibit_number(index: int) -> str:
    return f"EX-{index + 1:02d}"


def _make_finding_id(index: int) -> str:
    return f"F-{index + 1:03d}"


def recover_files(
    scan_id: int,
    inodes: list[int],
    db: Session,
) -> list[dict[str, Any]]:
    """Recover listed inodes from the evidence associated with the scan."""
    scan = db.get(Scan, scan_id)
    if not scan:
        raise ValueError(f"Scan {scan_id} not found")

    evidence_path = scan.evidence_path
    output_base = Path("case") / f"scan_{scan_id}" / "recovered"
    output_base.mkdir(parents=True, exist_ok=True)

    # Load candidates to get metadata
    candidates: list[dict] = []
    if scan.candidates_json:
        candidates = json.loads(scan.candidates_json)
    candidates_by_inode = {c["inode"]: c for c in candidates}

    # Check for existing recoveries to assign exhibit numbers
    existing_count = db.query(Recovery).filter(Recovery.scan_id == scan_id).count()

    results = []
    sha_seen: dict[str, int] = {}  # sha256 → inode (for duplicate detection)

    # Load existing sha set
    for rec in db.query(Recovery).filter(Recovery.scan_id == scan_id).all():
        if rec.sha256:
            sha_seen[rec.sha256] = rec.inode

    for i, inode in enumerate(inodes):
        idx = existing_count + i
        exhibit = _make_exhibit_number(idx)
        finding = _make_finding_id(idx)
        candidate = candidates_by_inode.get(inode, {})

        try:
            from ext4recover.evidence import open_evidence
            from ext4recover.tsk import open_fs
            from ext4recover.recovery import recover_inode

            evidence = open_evidence(evidence_path)
            stream = evidence.analysis_path
            fs = open_fs(stream, 0)

            output_path, validation = recover_inode(fs, inode, output_base)
            v = validation.json()

            sha256 = v.get("sha256", "")
            duplicate_of = sha_seen.get(sha256)

            if sha256 and sha256 not in sha_seen:
                sha_seen[sha256] = inode

            name = candidate.get("name")
            file_path = candidate.get("path")
            name_source = candidate.get("name_source", "none")

            status_map = {"FULL": "FULL", "PARTIAL": "PARTIAL"}
            status = status_map.get(v.get("status", ""), "FAILED")

            rec = Recovery(
                scan_id=scan_id,
                inode=inode,
                file_name=name,
                file_path=file_path,
                size_bytes=v.get("recovered_size"),
                expected_size=v.get("expected_size"),
                sha256=sha256,
                signature=v.get("signature"),
                status=status,
                output_path=str(output_path),
                name_source=name_source,
                duplicate_of_inode=duplicate_of,
                exhibit_number=exhibit,
                finding_id=finding,
                created_at=datetime.now(timezone.utc),
            )
            db.add(rec)
            db.commit()
            db.refresh(rec)

            results.append({
                "id": rec.id,
                "inode": inode,
                "exhibit_number": exhibit,
                "finding_id": finding,
                "file_name": name,
                "file_path": file_path,
                "size_bytes": v.get("recovered_size"),
                "expected_size": v.get("expected_size"),
                "sha256": sha256,
                "status": status,
                "output_path": str(output_path),
                "name_source": name_source,
                "duplicate_of_inode": duplicate_of,
                "error": None,
            })

        except Exception as exc:
            results.append({
                "inode": inode,
                "exhibit_number": exhibit,
                "finding_id": finding,
                "status": "FAILED",
                "error": str(exc),
            })

    return results
