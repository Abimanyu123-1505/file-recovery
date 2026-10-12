"""Regression tests for Phase 3: Integrity and Evidence Handling (Findings I1 - I5).

I1: Chunked hash calculation, progress tracking, and cooperative cancellation.
I2: Evidence write-protection: open_evidence rejects output dir / DB paths.
I3: Immutable audit ledger with fail-closed guarantee.
I4: Output directory isolation and collision avoidance with _dup discriminators.
I5: Memory-bounded streaming recovery with 8 MiB max buffer.
"""

from unittest.mock import MagicMock
from pathlib import Path
import pytest

from ext4recover.hashing import sha256_file
from ext4recover.evidence import open_evidence, EvidenceError
from app.database import Base, record_audit, AuditEntry, SessionLocal, engine
from ext4recover.recovery import recover_inode, recover_inode_stream


def test_i1_chunked_hashing_and_cancellation(tmp_path):
    """I1: Chunked hash calculation with progress callback and cooperative cancellation."""
    test_file = tmp_path / "test.bin"
    content = b"A" * (256 * 1024)  # 256 KiB
    test_file.write_bytes(content)

    progress_reports = []
    def on_progress(done, total):
        progress_reports.append((done, total))

    # Test full calculation with small chunk size
    result = sha256_file(test_file, chunk_size=64 * 1024, progress_callback=on_progress)
    assert len(result) == 64
    assert len(progress_reports) >= 4
    assert progress_reports[-1][0] == len(content)

    # Test cooperative cancellation
    with pytest.raises(RuntimeError, match="cancelled"):
        sha256_file(test_file, chunk_size=32 * 1024, check_cancelled=lambda: True)


def test_i2_evidence_path_protection(tmp_path):
    """I2: Reject evidence paths that resolve to the output directory or database."""
    out_dir = tmp_path / "case_output"
    out_dir.mkdir()
    fake_ev = out_dir / "evidence_inside_output.img"
    fake_ev.write_bytes(b"dummy")

    db_file = tmp_path / "workbench.db"
    db_file.write_bytes(b"dummy_db")

    # Reject if evidence is inside output directory
    with pytest.raises(EvidenceError, match="output directory"):
        open_evidence(fake_ev, output_dir=out_dir)

    # Reject if evidence matches database path
    with pytest.raises(EvidenceError, match="database"):
        open_evidence(db_file, db_path=db_file)


def test_i3_audit_ledger_fail_closed():
    """I3: Audit ledger writes immutable entries; fails closed on error."""
    import app.database as db_mod

    db_mod.init_db()
    db_session = db_mod.SessionLocal()
    try:
        entry = record_audit(
            db_session,
            action="scan_start",
            examiner_id="EX-007",
            target="evidence.raw",
            input_hash="11223344",
            details="Initial scan launched",
        )
        assert entry.id is not None
        assert entry.action == "scan_start"
        assert entry.examiner_id == "EX-007"

        # Verify queryable from DB
        found = db_session.get(AuditEntry, entry.id)
        assert found is not None
        assert found.input_hash == "11223344"

        # Simulate failure to ensure fail-closed behavior
        bad_session = MagicMock()
        bad_session.commit.side_effect = Exception("DB disk I/O error")
        with pytest.raises(RuntimeError, match="Fail-closed"):
            record_audit(bad_session, action="report_export")
    finally:
        db_session.close()


def test_i4_collision_discriminator(tmp_path):
    """I4: Recoveries never overwrite existing files without appending unique discriminators."""
    from ext4recover.recovery import get_unique_output_path

    out_dir = tmp_path / "test_recovered"
    out_dir.mkdir(parents=True, exist_ok=True)

    file1 = get_unique_output_path(out_dir, "document.pdf")
    file1.write_text("v1")
    assert file1.name == "document.pdf"

    file2 = get_unique_output_path(out_dir, "document.pdf")
    file2.write_text("v2")
    assert file2.name == "document_dup1.pdf"

    file3 = get_unique_output_path(out_dir, "document.pdf")
    file3.write_text("v3")
    assert file3.name == "document_dup2.pdf"


def test_i5_memory_bounded_streaming_recovery(tmp_path):
    """I5: Inode recovery enforces bounded chunks and streaming writes."""
    mock_entry = MagicMock()
    # Simulate a 16 MiB deleted file
    total_size = 16 * 1024 * 1024
    mock_entry.info.meta.size = total_size

    chunk_size_record = []
    def mock_read_random(offset, size):
        chunk_size_record.append(size)
        return b"Z" * min(size, total_size - offset)

    mock_entry.read_random.side_effect = mock_read_random
    mock_fs = MagicMock()
    mock_fs.open_meta.return_value = mock_entry

    out_file, val = recover_inode_stream(
        mock_fs, inode=55, output_dir=tmp_path, buffer_size=8 * 1024 * 1024
    )

    assert val.recovered_size == total_size
    assert val.status == "FULL"
    # Verify no chunk exceeded 8 MiB
    assert all(c <= 8 * 1024 * 1024 for c in chunk_size_record)
    assert len(chunk_size_record) >= 2
    assert out_file.exists()
    assert out_file.stat().st_size == total_size
