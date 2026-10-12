"""Regression tests for Findings R1, R2, R3 (Reporting Integrity).

R1: Chain-of-custody table with acquisition date, examiner, intake hash, post-scan hash, match status, tool version.
R2: Scan configuration in report for reproducibility.
R3: Export timestamp in UTC ISO 8601 (YYYY-MM-DDTHH:MM:SSZ).
"""

from pathlib import Path
import re
import pytest
from unittest.mock import MagicMock

from app.services.report_builder import build_report
from app.services.docx_report import generate_docx


def test_r1_and_r2_report_builder_metadata():
    """R1 & R2: report builder must produce chain_of_custody and scan_configuration."""
    mock_scan = MagicMock()
    mock_scan.id = 101
    mock_scan.evidence_path = "/path/to/evidence.raw"
    mock_scan.evidence_sha256_pre = "a" * 64
    mock_scan.evidence_sha256_post = "a" * 64
    mock_scan.integrity_ok = True
    mock_scan.status = "complete"
    mock_scan.created_at = None
    mock_scan.completed_at = None

    mock_case = MagicMock()
    mock_case.case_number = "CASE-2026-001"
    mock_case.case_title = "The Test Case"
    mock_case.examiner_name = "Detective Miller"
    mock_case.rank_badge = "Badge #404"
    mock_case.department = "Digital Forensics Unit"
    mock_case.requesting_authority = "Chief of Police"
    mock_case.date_received = "2026-03-01"
    mock_case.notes = "Sample"

    report = build_report(
        scan=mock_scan,
        case=mock_case,
        recoveries=[],
        candidates=[],
    )

    # R1: Chain of custody
    assert "chain_of_custody" in report
    coc = report["chain_of_custody"]
    assert coc["acquisition_date"] == "2026-03-01"
    assert coc["examiner"] == "Detective Miller"
    assert coc["intake_hash"] == "a" * 64
    assert coc["post_scan_hash"] == "a" * 64
    assert "MATCH" in coc["match_status"]
    assert "tool_version" in coc

    # R2: Scan configuration
    assert "scan_configuration" in report
    cfg = report["scan_configuration"]
    assert cfg["scan_id"] == 101
    assert cfg["hash_chunk_size_bytes"] == 1024 * 1024
    assert cfg["read_only_enforced"] is True

    # R3: UTC ISO 8601 timestamp ending in Z
    assert "generated_at_utc" in report
    iso_pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
    assert re.match(iso_pattern, report["generated_at_utc"])


def test_r1_and_r2_docx_output_contains_custody_and_config():
    """Verify DOCX generation renders chain of custody and scan configuration."""
    mock_scan = MagicMock()
    mock_scan.id = 102
    mock_scan.evidence_path = "/evidence.raw"
    mock_scan.evidence_sha256_pre = "b" * 64
    mock_scan.evidence_sha256_post = "b" * 64
    mock_scan.integrity_ok = True
    mock_scan.status = "complete"
    mock_scan.created_at = None
    mock_scan.completed_at = None

    mock_case = MagicMock()
    mock_case.case_number = "CASE-2026-002"
    mock_case.examiner_name = "Special Agent Dale"
    mock_case.date_received = "2026-03-05"
    mock_case.notes = ""

    report = build_report(
        scan=mock_scan,
        case=mock_case,
        recoveries=[],
        candidates=[],
    )

    docx_bytes = generate_docx(report)
    assert len(docx_bytes) > 1000
    # DOCX is a zip file containing word/document.xml
    import zipfile
    import io
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
        doc_xml = z.read("word/document.xml").decode("utf-8")
        assert "Special Agent Dale" in doc_xml
        assert "2026-03-05" in doc_xml
        assert "MATCH" in doc_xml
        assert "Scan Configuration" in doc_xml
