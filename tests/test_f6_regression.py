"""Regression tests for Finding F6.

F6: In the report builder, replace the single 'Deleted Files Found' card with honest counts:
(a) Total candidates scanned,
(b) Valid deletion records (plausible timestamp, links=0),
(c) Orphan/uncertain records,
(d) Candidates with surviving extents (recoverable=1),
(e) Inodes with cleared pointers (recoverable=0).
Clearly label which are facts and which are tool inferences.
"""

from unittest.mock import MagicMock
from datetime import datetime, timezone
import pytest

from backend.app.services.report_builder import build_report


def test_f6_honest_candidate_counts():
    mock_scan = MagicMock()
    mock_scan.evidence_path = "/tmp/test.img"
    mock_scan.evidence_sha256_pre = "abc"
    mock_scan.evidence_sha256_post = "abc"
    mock_scan.created_at = datetime.now(timezone.utc)
    mock_scan.completed_at = datetime.now(timezone.utc)

    mock_case = MagicMock()
    mock_case.date_received = None

    candidates = [
        # 1: Valid deletion, surviving extents (recoverable=1)
        {
            "inode": 12,
            "category": "deleted",
            "links_count": 0,
            "size": 1024,
            "can_recover": True,
            "recoverable": 1,
        },
        # 2: Inode with cleared pointers (recoverable=0)
        {
            "inode": 13,
            "category": "deleted",
            "links_count": 0,
            "size": 0,
            "can_recover": False,
            "recoverable": 0,
        },
        # 3: Orphan / uncertain record
        {
            "inode": 14,
            "category": "orphan/uncertain",
            "links_count": 0,
            "size": 2048,
            "can_recover": True,
            "recoverable": 1,
        },
    ]

    report = build_report(mock_scan, mock_case, recoveries=[], candidates=candidates)

    cs = report["candidate_summary"]
    # (a) Total candidates scanned
    assert cs["total_scanned"]["count"] == 3
    assert cs["total_scanned"]["type"] == "fact"

    # (b) Valid deletion records
    assert cs["valid_deletion_records"]["count"] == 2
    assert cs["valid_deletion_records"]["type"] == "tool_inference"

    # (c) Orphan/uncertain records
    assert cs["orphan_uncertain_records"]["count"] == 1
    assert cs["orphan_uncertain_records"]["type"] == "tool_inference"

    # (d) Surviving extents
    assert cs["surviving_extents"]["count"] == 2
    assert cs["surviving_extents"]["type"] == "fact"

    # (e) Cleared pointers
    assert cs["cleared_pointers"]["count"] == 1
    assert cs["cleared_pointers"]["type"] == "fact"
