"""FastAPI application – EXT4 Recovery Workbench backend."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from .database import Case, Recovery, Scan, SessionLocal, get_db, init_db, record_audit
from .schemas import (
    CaseCreate,
    CaseOut,
    EvidenceCheckOut,
    EvidenceListOut,
    RecoverRequest,
    RecoveryOut,
    ReportRequest,
    ScanOut,
    ScanRequest,
)
from .services.scanner import STAGES, cancel_scan, run_scan
from .services.recovery_service import recover_files
from .services.report_builder import build_report
from .services.docx_report import generate_docx

app = FastAPI(
    title="EXT4 Recovery Workbench API",
    description="Read-only EXT4 forensic analysis for law enforcement use.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

EVIDENCE_DIR = os.environ.get("EVIDENCE_DIR", "")

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _case_or_404(case_id: int, db: Session) -> Case:
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return case


def _scan_or_404(scan_id: int, db: Session) -> Scan:
    scan = db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")
    return scan


# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "time_utc": datetime.now(timezone.utc).isoformat()}


# ─────────────────────────────────────────────────────────────────────────────
# Cases
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/cases", response_model=CaseOut, status_code=201)
def create_case(payload: CaseCreate, db: Session = Depends(get_db)):
    case = Case(**payload.model_dump())
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


@app.get("/api/cases", response_model=list[CaseOut])
def list_cases(db: Session = Depends(get_db)):
    return db.query(Case).order_by(Case.created_at.desc()).all()


@app.get("/api/cases/{case_id}", response_model=CaseOut)
def get_case(case_id: int, db: Session = Depends(get_db)):
    return _case_or_404(case_id, db)


@app.patch("/api/cases/{case_id}", response_model=CaseOut)
def update_case(case_id: int, payload: CaseCreate, db: Session = Depends(get_db)):
    case = _case_or_404(case_id, db)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(case, field, value)
    db.commit()
    db.refresh(case)
    return case


# ─────────────────────────────────────────────────────────────────────────────
# Evidence
# ─────────────────────────────────────────────────────────────────────────────

_EXT4_MAGIC = b"\x53\xef"  # bytes 56-57 of the superblock at offset 1024+56

def _check_ext4_magic(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            f.seek(1024 + 56)
            magic = f.read(2)
            return magic == _EXT4_MAGIC
    except Exception:
        return False


@app.get("/api/evidence/check", response_model=EvidenceCheckOut)
def check_evidence(path: str = Query(...)):
    p = Path(path)
    exists = p.exists()
    is_file = p.is_file() if exists else False
    size = p.stat().st_size if is_file else None
    readable = False
    looks_like_ext4 = False
    error = None
    friendly = ""

    if not exists:
        error = "File not found. Check the path and try again."
        friendly = "We could not find that file. Please check the path and try again."
    elif not is_file:
        error = "Path is a directory, not a file."
        friendly = "That path points to a folder, not a file. Please select an evidence image file."
    else:
        try:
            with p.open("rb") as f:
                f.read(1)
            readable = True
        except PermissionError:
            error = "Permission denied. Cannot read the file."
            friendly = "Access was denied. You may need to run the Workbench as an administrator."
        except Exception as exc:
            error = str(exc)
            friendly = f"Could not open the file: {exc}"

        if readable:
            looks_like_ext4 = _check_ext4_magic(p)
            if not looks_like_ext4:
                friendly = (
                    "This file does not appear to be an EXT4 image. "
                    "It may be a different format, or the file may be damaged."
                )
            else:
                size_mb = (size or 0) / (1024 * 1024)
                friendly = f"Evidence file found. Size: {size_mb:.1f} MB. EXT4 file system detected."

    return EvidenceCheckOut(
        path=str(p),
        exists=exists,
        is_file=is_file,
        size=size,
        readable=readable,
        looks_like_ext4=looks_like_ext4,
        friendly_description=friendly,
        error=error,
    )


@app.get("/api/evidence/list", response_model=EvidenceListOut)
def list_evidence():
    if not EVIDENCE_DIR:
        return EvidenceListOut(files=[])
    base = Path(EVIDENCE_DIR)
    if not base.is_dir():
        return EvidenceListOut(files=[])
    exts = {".img", ".dd", ".raw", ".bin", ".e01"}
    files = []
    for f in base.iterdir():
        if f.is_file() and f.suffix.lower() in exts:
            files.append({
                "name": f.name,
                "path": str(f),
                "size": f.stat().st_size,
            })
    return EvidenceListOut(files=sorted(files, key=lambda x: x["name"]))


# ─────────────────────────────────────────────────────────────────────────────
# Scans
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/scans", response_model=ScanOut, status_code=201)
async def start_scan(payload: ScanRequest, db: Session = Depends(get_db)):
    _case_or_404(payload.case_id, db)
    p = Path(payload.evidence_path)
    if not p.is_file():
        raise HTTPException(
            status_code=422,
            detail="Evidence file not found. Please use /api/evidence/check first.",
        )
    scan = Scan(
        case_id=payload.case_id,
        evidence_path=str(p.resolve()),
        status="pending",
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)
    output_dir = str(Path("case") / f"scan_{scan.id}")
    asyncio.create_task(run_scan(scan.id, str(p.resolve()), output_dir))
    return scan


@app.get("/api/scans/{scan_id}", response_model=ScanOut)
def get_scan(scan_id: int, db: Session = Depends(get_db)):
    return _scan_or_404(scan_id, db)


@app.get("/api/scans/{scan_id}/candidates")
def get_candidates(scan_id: int, db: Session = Depends(get_db)):
    scan = _scan_or_404(scan_id, db)
    if not scan.candidates_json:
        return {"candidates": [], "summary": {}}
    candidates = json.loads(scan.candidates_json)
    total = len(candidates)
    recoverable = sum(1 for c in candidates if c.get("can_recover"))
    return {
        "candidates": candidates,
        "summary": {
            "total": total,
            "recoverable": recoverable,
            "confirmed_names": sum(1 for c in candidates if c.get("name_confidence") == "confirmed"),
            "uncertain_names": sum(1 for c in candidates if c.get("name_confidence") == "uncertain"),
        },
    }


@app.post("/api/scans/{scan_id}/cancel")
def cancel_scan_endpoint(scan_id: int, db: Session = Depends(get_db)):
    scan = _scan_or_404(scan_id, db)
    cancel_scan(scan_id)
    return {"status": "cancel_requested"}


async def _scan_event_stream(scan_id: int) -> AsyncGenerator[str, None]:
    """Server-sent events stream of scan progress."""
    prev_stage = None
    prev_status = None
    db = SessionLocal()
    try:
        for _ in range(600):  # max 10 minutes at 1s intervals
            await asyncio.sleep(1)
            scan = db.get(Scan, scan_id)
            if scan is None:
                yield f"data: {json.dumps({'error': 'Scan not found'})}\n\n"
                break
            db.refresh(scan)
            payload = {
                "scan_id": scan_id,
                "status": scan.status,
                "stage": scan.stage,
                "stage_index": scan.stage_index,
                "stage_total": scan.stage_total,
                "integrity_ok": scan.integrity_ok,
            }
            if scan.stage != prev_stage or scan.status != prev_status:
                yield f"data: {json.dumps(payload)}\n\n"
                prev_stage = scan.stage
                prev_status = scan.status
            if scan.status in ("complete", "failed", "cancelled"):
                yield f"data: {json.dumps({**payload, 'done': True})}\n\n"
                break
    finally:
        db.close()


@app.get("/api/scans/{scan_id}/stream")
async def scan_stream(scan_id: int):
    return StreamingResponse(
        _scan_event_stream(scan_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Recovery
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/recover")
def recover(payload: RecoverRequest, db: Session = Depends(get_db)):
    scan = _scan_or_404(payload.scan_id, db)
    if scan.status != "complete":
        raise HTTPException(
            status_code=409,
            detail="Analysis must be complete before recovery.",
        )
    if scan.integrity_ok is False:
        raise HTTPException(
            status_code=409,
            detail="Evidence integrity check failed. Recovery is disabled. Contact your supervisor.",
        )
    results = recover_files(payload.scan_id, payload.inodes, db)
    return {"results": results}


@app.get("/api/scans/{scan_id}/recoveries", response_model=list[RecoveryOut])
def list_recoveries(scan_id: int, db: Session = Depends(get_db)):
    _scan_or_404(scan_id, db)
    return db.query(Recovery).filter(Recovery.scan_id == scan_id).all()


# ─────────────────────────────────────────────────────────────────────────────
# Reports
# ─────────────────────────────────────────────────────────────────────────────

def _build_report_data(scan_id: int, payload: ReportRequest, db: Session) -> dict:
    scan = _scan_or_404(scan_id, db)
    case = _case_or_404(scan.case_id, db)
    recoveries = db.query(Recovery).filter(Recovery.scan_id == scan_id).all()
    candidates: list[dict] = []
    if scan.candidates_json:
        candidates = json.loads(scan.candidates_json)
    declaration = payload.declaration.model_dump() if payload.declaration else None
    return build_report(scan, case, recoveries, candidates, payload.profile, payload.report_type, declaration)


@app.post("/api/reports/{scan_id}/json")
def report_json(scan_id: int, payload: ReportRequest, db: Session = Depends(get_db)):
    data = _build_report_data(scan_id, payload, db)
    examiner = data.get("case", {}).get("examiner_name")
    record_audit(
        db,
        action="report_export",
        examiner_id=examiner,
        target=f"scan:{scan_id}",
        details=f"Exported JSON report ({payload.report_type})",
    )
    return data


@app.post("/api/reports/{scan_id}/docx")
def report_docx(scan_id: int, payload: ReportRequest, db: Session = Depends(get_db)):
    data = _build_report_data(scan_id, payload, db)
    docx_bytes = generate_docx(data)
    examiner = data.get("case", {}).get("examiner_name")
    record_audit(
        db,
        action="report_export",
        examiner_id=examiner,
        target=f"scan:{scan_id}",
        details=f"Exported DOCX report ({payload.report_type})",
    )
    case_no = data["case"].get("case_number", "case").replace("/", "-").replace(" ", "_")
    filename = f"report_{case_no}_{scan_id}.docx"
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.post("/api/reports/{scan_id}/refresh-artifacts")
def refresh_artifacts(scan_id: int, db: Session = Depends(get_db)):
    """Manually trigger artifact refresh (timeline update). Called before report generation."""
    scan = _scan_or_404(scan_id, db)
    # In a full implementation this would re-read the audit log. For now, returns current state.
    return {"status": "refreshed", "scan_id": scan_id, "scan_status": scan.status}
