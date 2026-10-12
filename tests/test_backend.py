"""Backend tests: new endpoints, report structure, DOCX smoke test."""

import json
import sys
from pathlib import Path

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import Base, engine, init_db


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    """Use a temporary database for each test."""
    import app.database as db_mod
    db_mod.DB_PATH = tmp_path / "test.db"
    db_mod.engine = __import__("sqlalchemy").create_engine(
        f"sqlite:///{db_mod.DB_PATH}",
        connect_args={"check_same_thread": False},
    )
    import sqlalchemy.orm as orm
    db_mod.SessionLocal = orm.sessionmaker(
        autocommit=False, autoflush=False, bind=db_mod.engine
    )
    db_mod.Base.metadata.create_all(bind=db_mod.engine)
    yield
    db_mod.Base.metadata.drop_all(bind=db_mod.engine)


import pytest_asyncio


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# ─────────────────────────────────────────────────────────────────────────────
# Health endpoint
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


# ─────────────────────────────────────────────────────────────────────────────
# Cases
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_case(client):
    payload = {
        "case_number": "TEST/2026/001",
        "case_title": "Test Case",
        "examiner_name": "Jane Doe",
        "rank_badge": "DC / Badge 1234",
        "department": "Digital Forensics",
        "requesting_authority": "Crown Court",
        "date_received": "2026-06-01",
        "notes": "Test notes",
    }
    resp = await client.post("/api/cases", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["case_number"] == "TEST/2026/001"
    assert data["examiner_name"] == "Jane Doe"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_case_missing_case_number(client):
    resp = await client.post("/api/cases", json={"case_title": "No number"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_cases_empty(client):
    resp = await client.get("/api/cases")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_case_not_found(client):
    resp = await client.get("/api/cases/9999")
    assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Evidence check
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_evidence_check_nonexistent(client):
    resp = await client.get("/api/evidence/check?path=/nonexistent/path/image.img")
    assert resp.status_code == 200
    data = resp.json()
    assert data["exists"] is False
    assert data["readable"] is False
    assert data["looks_like_ext4"] is False
    assert data["error"] is not None


@pytest.mark.asyncio
async def test_evidence_check_real_image(client, tmp_path):
    """A .img file without EXT4 magic should fail looks_like_ext4."""
    img = tmp_path / "fake.img"
    img.write_bytes(b"\x00" * 2048)
    resp = await client.get(f"/api/evidence/check?path={img}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["exists"] is True
    assert data["is_file"] is True
    assert data["readable"] is True
    assert data["looks_like_ext4"] is False


@pytest.mark.asyncio
async def test_evidence_list_no_dir(client):
    resp = await client.get("/api/evidence/list")
    assert resp.status_code == 200
    data = resp.json()
    assert "files" in data


# ─────────────────────────────────────────────────────────────────────────────
# Report builder
# ─────────────────────────────────────────────────────────────────────────────

def test_report_builder_basic():
    """Unit test the report builder with mock DB objects."""
    from app.services.report_builder import build_report
    from types import SimpleNamespace
    from datetime import datetime, timezone

    case = SimpleNamespace(
        case_number="TEST/001",
        case_title="Test",
        examiner_name="DC Jane Doe",
        rank_badge="DC/4821",
        department="DFU",
        requesting_authority="Crown Court",
        date_received="2026-01-01",
        notes="",
    )
    scan = SimpleNamespace(
        id=1,
        evidence_path="/tmp/test.img",
        evidence_sha256_pre="abc123",
        evidence_sha256_post="abc123",
        integrity_ok=True,
        status="complete",
        created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 6, 1, 1, tzinfo=timezone.utc),
    )
    report = build_report(scan, case, [], [], "general", "investigator", None)

    assert report["report_version"] == "1.0"
    assert report["report_profile"] == "general"
    assert report["case"]["case_number"] == "TEST/001"
    assert report["scan"]["integrity_ok"] is True
    assert "executive_bullets" in report["summary"]
    assert len(report["limitations"]) > 0
    # No lab02 content in general profile
    assert "Lab #02" not in str(report)
    assert "ORION" not in str(report)


def test_report_builder_lab02_profile():
    """lab02 profile includes the ORION appendix."""
    from app.services.report_builder import build_report
    from types import SimpleNamespace
    from datetime import datetime, timezone

    case = SimpleNamespace(
        case_number="L02/001", case_title="", examiner_name="", rank_badge="",
        department="", requesting_authority="", date_received="", notes="",
    )
    scan = SimpleNamespace(
        id=2, evidence_path="/tmp/lab02.img",
        evidence_sha256_pre="x", evidence_sha256_post="x", integrity_ok=True,
        status="complete",
        created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 6, 1, 1, tzinfo=timezone.utc),
    )
    report = build_report(scan, case, [], [], "lab02", "forensic", None)
    assert report["report_profile"] == "lab02"
    assert "lab02_appendix" in report
    assert "ORION" in report["lab02_appendix"]["project"]


def test_report_integrity_failure():
    """Integrity failure is reflected in the report."""
    from app.services.report_builder import build_report
    from types import SimpleNamespace
    from datetime import datetime, timezone

    case = SimpleNamespace(
        case_number="INT/001", case_title="", examiner_name="", rank_badge="",
        department="", requesting_authority="", date_received="", notes="",
    )
    scan = SimpleNamespace(
        id=3, evidence_path="/tmp/integrity.img",
        evidence_sha256_pre="aaa", evidence_sha256_post="bbb", integrity_ok=False,
        status="complete",
        created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 6, 1, 1, tzinfo=timezone.utc),
    )
    report = build_report(scan, case, [], [], "general", "investigator", None)
    assert report["scan"]["integrity_status"] == "failed"
    assert "WARNING" in report["scan"]["integrity_result"]


# ─────────────────────────────────────────────────────────────────────────────
# DOCX smoke test
# ─────────────────────────────────────────────────────────────────────────────

def test_docx_smoke():
    """DOCX is generated without error and contains key section headings."""
    from app.services.report_builder import build_report
    from app.services.docx_report import generate_docx
    from docx import Document
    from io import BytesIO
    from types import SimpleNamespace
    from datetime import datetime, timezone

    case = SimpleNamespace(
        case_number="DOCX/001", case_title="DOCX Test", examiner_name="DC Test",
        rank_badge="DC/0001", department="DFU", requesting_authority="Court",
        date_received="2026-01-01", notes="",
    )
    scan = SimpleNamespace(
        id=10, evidence_path="/tmp/docx_test.img",
        evidence_sha256_pre="abc", evidence_sha256_post="abc", integrity_ok=True,
        status="complete",
        created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 6, 1, 1, tzinfo=timezone.utc),
    )
    report_data = build_report(scan, case, [], [], "general", "investigator", None)
    docx_bytes = generate_docx(report_data)

    assert len(docx_bytes) > 1000, "DOCX should not be empty"

    doc = Document(BytesIO(docx_bytes))
    headings = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]

    expected = [
        "Executive Summary",
        "Scope and Authority",
        "Evidence and Chain of Custody",
        "Methodology",
        "Findings",
        "Timeline",
        "Interpretation",
        "Limitations",
        "Conclusion",
        "Examiner Declaration and Signature",
    ]
    for heading in expected:
        assert any(heading in h for h in headings), f"Missing heading: {heading!r}\nHeadings found: {headings}"
