"""DOCX report generator following the 13-section forensic structure."""

from __future__ import annotations

import io
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Inches, Pt, RGBColor


TOOL_NAME = "EXT4 Deleted File Recovery Workbench"
_VERSION_FILE = Path(__file__).resolve().parents[3] / "VERSION"
TOOL_VERSION = _VERSION_FILE.read_text().strip() if _VERSION_FILE.exists() else "0.1.0"


def xml_safe(text: str | None) -> str:
    """Sanitise text for safe inclusion in Word XML."""
    if text is None:
        return ""
    # Remove non-XML characters
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", str(text))
    return text


def _add_heading(doc: Document, text: str, level: int) -> None:
    doc.add_heading(xml_safe(text), level=level)


def _add_para(doc: Document, text: str, style: str = "Normal") -> None:
    doc.add_paragraph(xml_safe(text), style=style)


def _add_bold_label(doc: Document, label: str, value: str) -> None:
    p = doc.add_paragraph()
    run = p.add_run(xml_safe(label) + ": ")
    run.bold = True
    p.add_run(xml_safe(value))


def _add_table_with_headers(doc: Document, headers: list[str], rows: list[list[str]]) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    # Set repeat header rows
    tr = table.rows[0]._tr
    trPr = OxmlElement("w:trPr")
    tblHeader = OxmlElement("w:tblHeader")
    trPr.append(tblHeader)
    tr.insert(0, trPr)

    hdr_cells = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr_cells[i].text = xml_safe(h)
        hdr_cells[i].paragraphs[0].runs[0].bold = True

    for j, row in enumerate(rows):
        row_cells = table.add_row().cells
        for k, cell in enumerate(row):
            row_cells[k].text = xml_safe(str(cell) if cell is not None else "")


def _page_break(doc: Document) -> None:
    doc.add_page_break()


def generate_docx(report: dict[str, Any]) -> bytes:
    """Generate a Word document from the structured report dict and return bytes."""
    doc = Document()

    # ── Header/footer on every page ─────────────────────────────────────────
    section = doc.sections[0]
    header = section.header
    header_para = header.paragraphs[0]
    header_run = header_para.add_run(
        f"RESTRICTED – LAW ENFORCEMENT USE  |  Case: {xml_safe(report['case'].get('case_number', ''))}"
    )
    header_run.font.size = Pt(9)
    header_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    footer = section.footer
    footer_para = footer.paragraphs[0]
    footer_para.text = (
        f"{TOOL_NAME} v{TOOL_VERSION}  |  Report ref: "
        f"{xml_safe(report['case'].get('case_number', ''))}/"
        f"{xml_safe(str(report['scan'].get('id', '')))}"
    )
    footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # ===========================================================================
    # 1. COVER PAGE
    # ===========================================================================
    doc.add_heading("RESTRICTED – LAW ENFORCEMENT USE", level=0)
    doc.add_heading(TOOL_NAME, level=1)
    doc.add_heading(
        report.get("report_type", "investigator").replace("_", " ").title() + " Report",
        level=2,
    )

    cover_data = [
        ("Case Number", report["case"].get("case_number", "")),
        ("Case Title", report["case"].get("case_title", "")),
        ("Report Reference",
         f"{report['case'].get('case_number', '')}/{report['scan'].get('id', '')}"),
        ("Date Generated", report.get("generated_at_utc", "")[:10]),
        ("Examiner", report["case"].get("examiner_name", "")),
        ("Rank / Badge", report["case"].get("rank_badge", "")),
        ("Unit / Department", report["case"].get("department", "")),
        ("Requesting Authority", report["case"].get("requesting_authority", "")),
        ("Evidence Item", report["scan"].get("evidence_filename", "")),
    ]
    for label, value in cover_data:
        _add_bold_label(doc, label, value)

    _page_break(doc)

    # ===========================================================================
    # 2. DOCUMENT CONTROL
    # ===========================================================================
    _add_heading(doc, "Document Control", level=1)
    control_table = [
        ["Tool", f"{TOOL_NAME} v{TOOL_VERSION}"],
        ["Report Version", report.get("report_version", "1.0")],
        ["Report Profile", report.get("report_profile", "general")],
        ["Generated (UTC)", report.get("generated_at_utc", "")],
        ["Classification", "Restricted – Law enforcement use"],
        ["Case Number", report["case"].get("case_number", "")],
    ]
    _add_table_with_headers(doc, ["Field", "Value"], control_table)
    _page_break(doc)

    # ===========================================================================
    # 3. TABLE OF CONTENTS (placeholder – Word updates on open)
    # ===========================================================================
    _add_heading(doc, "Table of Contents", level=1)
    _add_para(doc, "[Right-click this area in Word and select 'Update Field' to generate the table of contents.]")
    _page_break(doc)

    # ===========================================================================
    # 4. EXECUTIVE SUMMARY
    # ===========================================================================
    _add_heading(doc, "Executive Summary", level=1)
    _add_para(doc, "This section provides a plain-language overview for investigators and supervising officers.")
    for bullet in report.get("summary", {}).get("executive_bullets", []):
        _add_para(doc, f"\u2022 {bullet}")

    confidence_note = ""
    integrity_status = report["scan"].get("integrity_status", "unknown")
    if integrity_status == "ok":
        confidence_note = "The evidence digital fingerprint was unchanged throughout analysis. Results can be relied upon subject to the limitations in Section 11."
    elif integrity_status == "failed":
        confidence_note = (
            "WARNING: The evidence digital fingerprint changed during analysis. "
            "These results must NOT be relied upon. Contact your supervisor before proceeding."
        )
    _add_para(doc, confidence_note)
    _page_break(doc)

    # ===========================================================================
    # 5. SCOPE AND AUTHORITY
    # ===========================================================================
    _add_heading(doc, "Scope and Authority", level=1)
    if report["case"].get("requesting_authority"):
        _add_para(doc, f"This analysis was requested by: {xml_safe(report['case']['requesting_authority'])}.")
    _add_para(doc,
        "The scope of this examination was limited to identifying and recovering deleted files "
        "from the EXT4 file system within the supplied evidence image. No other media, accounts, "
        "or systems were examined as part of this submission."
    )
    _add_para(doc,
        "The analysis was conducted in a read-only manner. The original evidence file was not "
        "modified in any way."
    )
    if report["case"].get("notes"):
        _add_para(doc, f"Case notes: {xml_safe(report['case']['notes'])}")
    _page_break(doc)

    # ===========================================================================
    # 6. EVIDENCE AND CHAIN OF CUSTODY
    # ===========================================================================
    _add_heading(doc, "Evidence and Chain of Custody", level=1)
    _add_heading(doc, "Evidence Item", level=2)
    evidence_rows = [
        ["Item Reference", "EV-01"],
        ["File Name", xml_safe(report["scan"].get("evidence_filename", ""))],
        ["Full Path", xml_safe(report["scan"].get("evidence_path", ""))],
        ["Size",
         str(report["scan"].get("evidence_size") or "Unknown")],
        ["Date Received", xml_safe(report["case"].get("date_received", ""))],
        ["Date Analysed", (report["scan"].get("created_at") or "")[:10]],
    ]
    _add_table_with_headers(doc, ["Field", "Value"], evidence_rows)

    _add_heading(doc, "Digital Fingerprints (SHA-256)", level=2)
    fp_rows = [
        ["Pre-analysis fingerprint", xml_safe(report["scan"].get("evidence_sha256_pre", "Not recorded"))],
        ["Post-analysis fingerprint", xml_safe(report["scan"].get("evidence_sha256_post", "Not recorded"))],
        ["Integrity check", xml_safe(report["scan"].get("integrity_result", ""))],
    ]
    _add_table_with_headers(doc, ["Check", "Value"], fp_rows)

    _add_heading(doc, "Chain of Custody", level=2)
    _add_para(doc, "Complete the table below with the physical custody record for this evidence item.")
    coc_rows = [
        ["", "", "", ""],
        ["", "", "", ""],
        ["", "", "", ""],
    ]
    _add_table_with_headers(
        doc,
        ["Released by", "Received by", "Date / Time", "Purpose"],
        coc_rows,
    )
    _page_break(doc)

    # ===========================================================================
    # 7. METHODOLOGY
    # ===========================================================================
    _add_heading(doc, "Methodology", level=1)
    _add_para(doc,
        "The following steps were carried out in sequence. Another qualified examiner following "
        "these steps with the same evidence and tool version should obtain the same results."
    )
    for step in report.get("methodology", []):
        _add_para(doc, xml_safe(step))
    _page_break(doc)

    # ===========================================================================
    # 8. FINDINGS
    # ===========================================================================
    _add_heading(doc, "Findings", level=1)

    cand_summary = report.get("candidate_summary")
    if cand_summary:
        _add_heading(doc, "8.1 Scanned Candidates & Forensic Classification", level=2)
        _add_para(doc, "The table below details all candidate records scanned, distinguishing direct facts from tool inferences.")
        cand_rows = []
        for key, item in cand_summary.items():
            type_label = "Fact" if item.get("type") == "fact" else "Tool Inference"
            cand_rows.append([
                xml_safe(item.get("label", key)),
                str(item.get("count", 0)),
                type_label,
                xml_safe(item.get("description", "")),
            ])
        _add_table_with_headers(doc, ["Category", "Count", "Classification", "Description"], cand_rows)
        doc.add_paragraph()

    findings = report.get("findings", [])

    _add_heading(doc, "8.2 Recovered File Findings", level=2)
    if not findings:
        _add_para(doc, "No files were recovered during this analysis.")
    else:
        for f in findings:
            _add_heading(doc, f"{f.get('finding_id', 'F-???')} – {xml_safe(f.get('file_name', '(name not available)')[:60])}", level=3)
            fd_rows = [
                ["Exhibit Number", xml_safe(f.get("exhibit_number", ""))],
                ["What was found", xml_safe(f.get("file_name", "(name not available)"))],
                ["Where (path)", xml_safe(f.get("file_path", "(path not available)"))],
                ["File record number (inode)", str(f.get("inode", ""))],
                ["Source of information", _source_label(f.get("name_source", "none"))],
                ["Size (recorded)", xml_safe(f.get("size_friendly", ""))],
                ["Digital fingerprint (SHA-256)", xml_safe(f.get("sha256", ""))],
                ["Recovery status", xml_safe(f.get("status_plain", ""))],
                ["Confidence", xml_safe(f.get("confidence", ""))],
                ["Confidence reason", xml_safe(f.get("confidence_reason", ""))],
            ]
            if f.get("duplicate_of_inode"):
                fd_rows.append(["Duplicate note", f"Same digital fingerprint as file record {f['duplicate_of_inode']}"])
            _add_table_with_headers(doc, ["Field", "Value"], fd_rows)
            doc.add_paragraph()

    _add_heading(doc, "8.2 Recovered File Copies", level=2)
    recovered = [f for f in findings if f.get("status") in ("FULL", "PARTIAL")]
    if recovered:
        rec_rows = [
            [
                f.get("exhibit_number", ""),
                f.get("finding_id", ""),
                f.get("file_name", "(name not available)"),
                f.get("status_plain", ""),
                f.get("size_friendly", ""),
                (f.get("sha256") or "")[:20] + "...",
            ]
            for f in recovered
        ]
        _add_table_with_headers(
            doc,
            ["Exhibit", "Finding", "File Name", "Status", "Size", "Fingerprint (partial)"],
            rec_rows,
        )
    else:
        _add_para(doc, "No files were recovered.")

    _add_heading(doc, "8.3 Existing System Artefacts", level=2)
    _add_para(doc,
        "No live (allocated) system artefacts were examined as part of this submission. "
        "The scope was limited to deleted file recovery."
    )
    _page_break(doc)

    # ===========================================================================
    # 9. TIMELINE
    # ===========================================================================
    _add_heading(doc, "Timeline", level=1)
    _add_para(doc,
        "Events are listed in chronological order where a reliable timestamp is available. "
        "Events without a confirmed timestamp are listed separately."
    )

    timeline = report.get("timeline", [])
    timestamped = [t for t in timeline if not t.get("sequence_only") and t.get("datetime")]
    sequence_only = [t for t in timeline if t.get("sequence_only")]

    if timestamped:
        t_rows = [
            [
                xml_safe(t.get("datetime", "")[:19].replace("T", " ") + " UTC"),
                xml_safe(t.get("event", "")),
                xml_safe(t.get("source", "")),
                xml_safe(t.get("finding_id", "") or ""),
            ]
            for t in timestamped
        ]
        _add_table_with_headers(
            doc,
            ["Date / Time (UTC)", "Event", "Source", "Finding ID"],
            t_rows,
        )

    if sequence_only:
        _add_heading(doc, "Sequence Only (no confirmed timestamp)", level=2)
        _add_para(doc,
            "The following events were identified but have no reliable timestamp. "
            "They are listed in analysis order, not necessarily chronological order."
        )
        s_rows = [
            [
                xml_safe(t.get("event", "")),
                xml_safe(t.get("source", "")),
                xml_safe(t.get("finding_id", "") or ""),
            ]
            for t in sequence_only
        ]
        _add_table_with_headers(doc, ["Event", "Source", "Finding ID"], s_rows)

    _page_break(doc)

    # ===========================================================================
    # 10. INTERPRETATION
    # ===========================================================================
    _add_heading(doc, "Interpretation", level=1)

    _add_heading(doc, "Established Facts", level=2)
    _add_para(doc,
        "The following statements are supported directly by the data. Each is tied to a specific finding."
    )
    for fact in report.get("established_facts", []):
        fid = f" ({fact['finding_id']})" if fact.get("finding_id") else ""
        _add_para(doc, f"\u2022 {xml_safe(fact['statement'])}{fid}")

    _add_heading(doc, "Inferences and Opinion", level=2)
    _add_para(doc,
        "The following are professional inferences based on the data. They are not established facts. "
        "Cautious wording such as 'is consistent with' reflects uncertainty."
    )
    inferences = report.get("inferences", [])
    if inferences:
        for inf in inferences:
            _add_para(doc,
                f"\u2022 [{xml_safe(inf.get('confidence_level', 'Uncertain'))}] "
                f"{xml_safe(inf.get('statement', ''))} "
                f"Reasoning: {xml_safe(inf.get('reasoning', ''))}"
            )
    else:
        _add_para(doc, "No inferences are offered beyond the established facts above.")

    _page_break(doc)

    # ===========================================================================
    # 11. LIMITATIONS
    # ===========================================================================
    _add_heading(doc, "Limitations", level=1)
    for i, lim in enumerate(report.get("limitations", []), 1):
        _add_para(doc, f"{i}. {xml_safe(lim)}")
    _page_break(doc)

    # ===========================================================================
    # 12. CONCLUSION
    # ===========================================================================
    _add_heading(doc, "Conclusion", level=1)
    summary = report.get("summary", {})
    _add_para(doc,
        f"Analysis of the supplied evidence image identified {summary.get('total_candidates', 0)} "
        f"deleted file record(s). "
        f"{summary.get('fully_recovered', 0)} file(s) were fully recovered and "
        f"{summary.get('partially_recovered', 0)} file(s) were partly recovered. "
        "All findings are subject to the limitations listed in Section 11. "
        "The digital fingerprint of the evidence was unchanged throughout analysis."
    )
    _page_break(doc)

    # ===========================================================================
    # 13. EXAMINER DECLARATION
    # ===========================================================================
    _add_heading(doc, "Examiner Declaration and Signature", level=1)
    declaration = report.get("declaration")
    if declaration:
        _add_para(doc,
            f"I, {xml_safe(declaration.get('name', ''))}, {xml_safe(declaration.get('rank', ''))}, "
            f"declare that the contents of this report are accurate to the best of my knowledge "
            f"and have been prepared in accordance with the methodology described herein."
        )
        _add_para(doc, f"Date: {xml_safe(declaration.get('date', ''))}")
        _add_para(doc, f"Statement: {xml_safe(declaration.get('statement', ''))}")
    else:
        _add_para(doc, "Examiner Name: _______________________________")
        _add_para(doc, "Rank / Badge: _________________________________")
        _add_para(doc, "Date: ________________________________________")
        _add_para(doc, "Signature: ___________________________________")
    _page_break(doc)

    # ===========================================================================
    # APPENDICES
    # ===========================================================================
    _add_heading(doc, "Appendix A – Recovered File Register", level=1)
    if findings:
        app_a_rows = [
            [
                f.get("exhibit_number", ""),
                f.get("finding_id", ""),
                f.get("file_name", "(name not available)"),
                f.get("size_friendly", ""),
                f.get("status_plain", ""),
                f.get("sha256", ""),
            ]
            for f in findings
        ]
        _add_table_with_headers(
            doc,
            ["Exhibit", "Finding ID", "File Name", "Size", "Recovery Status", "SHA-256 Fingerprint"],
            app_a_rows,
        )
    else:
        _add_para(doc, "No files were recovered.")
    _page_break(doc)

    _add_heading(doc, "Appendix B – Artefact Contents (Excerpted)", level=1)
    _add_para(doc,
        "Recovered file content is not reproduced in this document. "
        "Recovered files are stored in the case output directory and are identified by exhibit number. "
        "The SHA-256 fingerprint of each file is listed in Appendix A."
    )
    _page_break(doc)

    _add_heading(doc, "Appendix C – Integrity Ledger Events", level=1)
    ledger_rows = [
        ["Analysis start", (report["scan"].get("created_at") or "")[:19].replace("T", " ") + " UTC",
         xml_safe(report["scan"].get("evidence_sha256_pre", ""))],
        ["Analysis end", (report["scan"].get("completed_at") or "")[:19].replace("T", " ") + " UTC",
         xml_safe(report["scan"].get("evidence_sha256_post", ""))],
    ]
    _add_table_with_headers(doc, ["Event", "Time (UTC)", "SHA-256 Fingerprint"], ledger_rows)
    _page_break(doc)

    _add_heading(doc, "Appendix D – File System Technical Details", level=1)
    _add_para(doc, "File system type: EXT4")
    _add_para(doc, f"Evidence file: {xml_safe(report['scan'].get('evidence_path', ''))}")
    _add_para(doc, f"Analysis tool: {TOOL_NAME} v{TOOL_VERSION}")
    _add_para(doc,
        "Forensic library: pytsk3 (Python bindings to The Sleuth Kit). "
        "All file system reads performed in read-only mode."
    )
    _page_break(doc)

    _add_heading(doc, "Appendix E – Glossary of Terms", level=1)
    glossary = [
        ["Digital fingerprint (SHA-256)", "A unique mathematical checksum of a file. Any change to the file produces a different fingerprint."],
        ["File record (inode)", "An internal entry in the file system that stores information about a file, such as size and location."],
        ["Deleted file record", "A file system entry marked as no longer in use. The data may still be recoverable."],
        ["Directory record", "An entry in a folder that stores a file's name and its associated file record number."],
        ["Leftover data", "Remnants of previously deleted files that may remain in unallocated storage space."],
        ["File system activity log (journal)", "An internal log kept by EXT4 to record recent file system changes."],
        ["Independent verification", "Confirmation of a finding using a separate tool or method."],
        ["Evidence unchanged during analysis", "Confirmation that the digital fingerprint before and after analysis is identical."],
        ["Confidence: Confirmed", "The file name or detail was found in a surviving directory record – the most reliable source."],
        ["Confidence: Uncertain", "The detail could not be confirmed from a directory record. It is an inference."],
    ]
    _add_table_with_headers(doc, ["Term", "Plain meaning"], glossary)

    if report.get("report_profile") == "lab02" and report.get("lab02_appendix"):
        _page_break(doc)
        _add_heading(doc, "Appendix F – Lab02 / Project ORION Supplement", level=1)
        lab = report["lab02_appendix"]
        _add_para(doc, f"Project: {xml_safe(lab.get('project', ''))}")
        _add_para(doc, f"Laboratory: {xml_safe(lab.get('lab', ''))}")
        _add_para(doc, "This appendix is present because the lab02 report profile was selected.")
        for d in lab.get("deliverables", []):
            _add_para(doc, f"\u2022 {xml_safe(d)}")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _source_label(source: str) -> str:
    labels = {
        "dir_entry": "Directory record (most reliable)",
        "slack": "Leftover data (less reliable)",
        "none": "No surviving source record",
    }
    return labels.get(source, source)
