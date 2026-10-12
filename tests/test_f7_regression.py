"""Regression tests for Finding F7.

F7: Track seen SHA-256 hashes during recovery, mark duplicates in DB (duplicate_of_inode),
recover only unique content (or symlink duplicates in the output dir so disk space is not wasted),
and label them clearly in the report so an investigator isn't misled by repeated content.
"""

from unittest.mock import MagicMock
from datetime import datetime, timezone
from pathlib import Path
import pytest

from app.services.recovery_service import recover_files
from app.services.report_builder import build_report
from app.database import Recovery, Scan, Case


def test_f7_track_duplicates_in_recovery_and_report(tmp_path):
    # Mock database and filesystem
    mock_db = MagicMock()
    mock_fs = MagicMock()

    # Two candidates with the exact same content
    candidate_a = {"inode": 100, "name": "doc1.pdf", "path": "/doc1.pdf", "size": 100}
    candidate_b = {"inode": 101, "name": "doc2.pdf", "path": "/doc2.pdf", "size": 100}

    # Simulate recoveries
    rec_a = Recovery(
        id=1,
        scan_id=1,
        inode=100,
        file_name="doc1.pdf",
        sha256="abcdef123456",
        duplicate_of_inode=None,
        status="FULL",
        size_bytes=100,
        expected_size=100,
        created_at=datetime.now(timezone.utc),
    )
    rec_b = Recovery(
        id=2,
        scan_id=1,
        inode=101,
        file_name="doc2.pdf",
        sha256="abcdef123456",
        duplicate_of_inode=100,  # Duplicate of inode 100!
        status="FULL",
        size_bytes=100,
        expected_size=100,
        created_at=datetime.now(timezone.utc),
    )

    mock_scan = MagicMock()
    mock_scan.evidence_path = str(tmp_path / "test.img")
    mock_scan.evidence_sha256_pre = "hash"
    mock_scan.evidence_sha256_post = "hash"
    mock_scan.created_at = datetime.now(timezone.utc)
    mock_scan.completed_at = datetime.now(timezone.utc)

    mock_case = MagicMock()
    mock_case.date_received = None

    report = build_report(
        scan=mock_scan,
        case=mock_case,
        recoveries=[rec_a, rec_b],
        candidates=[candidate_a, candidate_b],
    )

    findings = report["findings"]
    assert len(findings) == 2
    assert findings[0]["duplicate_of_inode"] is None
    assert findings[0]["is_duplicate"] is False

    assert findings[1]["duplicate_of_inode"] == 100
    assert findings[1]["is_duplicate"] is True
    assert "Identical content" in findings[1]["duplicate_note"]
    assert "100" in findings[1]["duplicate_note"]
