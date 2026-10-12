/**
 * Step 6 – Report
 * Report builder with type selection, checklist, HTML preview, declaration, and downloads.
 */
import { useEffect, useState } from 'react';
import { useWorkbench } from '../context/WorkbenchContext';
import api from '../lib/api';
import { formatDate, friendlyError } from '../lib/glossary';

function ChecklistItem({ ok, warn, label }) {
  if (ok) return (
    <li className="checklist-item">
      <span className="checklist-icon checklist-icon--ok" aria-label="Complete">✓</span>
      <span>{label}</span>
    </li>
  );
  return (
    <li className="checklist-item">
      <span className="checklist-icon checklist-icon--warn" aria-label="Warning">⚠</span>
      <span style={{ color: 'var(--color-caution)' }}>{label}</span>
    </li>
  );
}

function ReportPreview({ data }) {
  if (!data) return null;
  const c = data.case || {};
  const s = data.summary || {};
  const findings = data.findings || [];
  return (
    <div className="report-preview" aria-label="Report preview">
      <div style={{ textAlign: 'center', borderBottom: '2px solid var(--color-border)', paddingBottom: '16px', marginBottom: '16px' }}>
        <div style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--color-text-secondary)' }}>RESTRICTED – LAW ENFORCEMENT USE</div>
        <h1 style={{ fontSize: '18px', fontWeight: 700, margin: '8px 0 4px' }}>EXT4 Deleted File Recovery Workbench</h1>
        <h2 style={{ fontSize: '14px', fontWeight: 400 }}>
          {data.report_type === 'investigator' ? 'Investigator Summary Report' : 'Full Forensic Report'}
        </h2>
      </div>
      <table style={{ width: '100%', fontSize: '13px', borderCollapse: 'collapse', marginBottom: '16px' }}>
        <tbody>
          {[
            ['Case Number', c.case_number],
            ['Case Title', c.case_title],
            ['Examiner', `${c.examiner_name || ''} ${c.rank_badge ? `(${c.rank_badge})` : ''}`.trim()],
            ['Department', c.department],
            ['Requesting Authority', c.requesting_authority],
            ['Date Generated', formatDate(data.generated_at_utc)],
          ].map(([label, val]) => val ? (
            <tr key={label} style={{ borderBottom: '1px solid var(--color-border)' }}>
              <td style={{ fontWeight: 600, width: '40%', padding: '4px 8px' }}>{label}</td>
              <td style={{ padding: '4px 8px' }}>{val}</td>
            </tr>
          ) : null)}
        </tbody>
      </table>

      <h2>Executive Summary</h2>
      <ul style={{ paddingLeft: '20px', lineHeight: 1.8 }}>
        {(s.executive_bullets || []).map((b, i) => <li key={i}>{b}</li>)}
      </ul>

      {findings.length > 0 && (
        <>
          <h2>Findings ({findings.length})</h2>
          {findings.map(f => (
            <div key={f.finding_id} style={{ borderLeft: '3px solid var(--color-border)', paddingLeft: '12px', marginBottom: '12px' }}>
              <strong>{f.finding_id} – {f.file_name}</strong>
              <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>
                {f.file_path} | {f.size_friendly} | {f.status_plain}
              </div>
            </div>
          ))}
        </>
      )}

      <h2>Limitations</h2>
      <ol style={{ paddingLeft: '20px', lineHeight: 1.8, fontSize: '13px' }}>
        {(data.limitations || []).map((l, i) => <li key={i}>{l}</li>)}
      </ol>

      {data.declaration && (
        <>
          <h2>Examiner Declaration</h2>
          <p>
            I, {data.declaration.name}, {data.declaration.rank}, {data.declaration.statement}.<br />
            Date: {data.declaration.date}
          </p>
        </>
      )}
    </div>
  );
}

export default function Report() {
  const { state } = useWorkbench();
  const caseData = state.caseData || {};
  const recoveries = state.recoveries || [];
  const candidates = state.candidates || [];

  const [reportType, setReportType] = useState('investigator');
  const [profile] = useState(state.reportProfile || 'general');
  const [declaration, setDeclaration] = useState({
    name: caseData.examiner_name || '',
    rank: caseData.rank_badge || '',
    date: new Date().toISOString().slice(0, 10),
    statement: 'I confirm the contents are accurate to the best of my knowledge',
  });

  const [previewData, setPreviewData] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [downloadingDocx, setDownloadingDocx] = useState(false);
  const [downloadingJson, setDownloadingJson] = useState(false);
  const [error, setError] = useState(null);
  const [declarationComplete, setDeclarationComplete] = useState(false);

  const hasCase = !!state.caseId;
  const hasRecoveries = recoveries.length > 0;
  const hasDeclaration = declaration.name && declaration.rank && declaration.date;

  const checklist = [
    { ok: hasCase, label: hasCase ? 'Case details completed' : 'Case details not completed – go back to Step 1' },
    { ok: !!state.scanId, label: !!state.scanId ? 'Analysis completed' : 'Analysis not yet run' },
    { ok: candidates.length > 0, label: candidates.length > 0 ? `${candidates.length} deleted file records found` : 'No deleted files found' },
    { ok: hasRecoveries, label: hasRecoveries ? `${recoveries.length} file(s) recovered` : 'No files recovered yet – you can still generate a report' },
    { ok: !!declaration.name, label: declaration.name ? 'Examiner name provided' : 'Examiner declaration not completed' },
    { ok: !!caseData.requesting_authority, label: caseData.requesting_authority ? 'Requesting authority recorded' : 'Requesting authority not recorded (recommended)' },
  ];

  async function loadPreview() {
    setLoadingPreview(true);
    setError(null);
    try {
      await api.refreshArtifacts(state.scanId).catch(() => {});
      const data = await api.reportJson(state.scanId, {
        scan_id: state.scanId,
        profile,
        report_type: reportType,
        declaration: hasDeclaration ? declaration : null,
      });
      setPreviewData(data);
    } catch (err) {
      const { friendly } = friendlyError(err);
      setError(friendly);
    } finally {
      setLoadingPreview(false);
    }
  }

  async function downloadDocx() {
    setDownloadingDocx(true);
    setError(null);
    try {
      const { blob, filename } = await api.reportDocx(state.scanId, {
        scan_id: state.scanId,
        profile,
        report_type: reportType,
        declaration: hasDeclaration ? declaration : null,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      const { friendly } = friendlyError(err);
      setError(friendly);
    } finally {
      setDownloadingDocx(false);
    }
  }

  async function downloadJson() {
    setDownloadingJson(true);
    setError(null);
    try {
      const data = await api.reportJson(state.scanId, {
        scan_id: state.scanId,
        profile,
        report_type: reportType,
        declaration: hasDeclaration ? declaration : null,
      });
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `report_${state.scanId}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      const { friendly } = friendlyError(err);
      setError(friendly);
    } finally {
      setDownloadingJson(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <div className="page-header-step">Step 6 of 6</div>
        <h1>Generate report</h1>
        <p className="page-header-description">
          Choose the report type, complete the examiner declaration, preview the report, then download it.
        </p>
      </div>

      {error && (
        <div className="alert alert--danger" role="alert">
          <span className="alert-icon">⚠</span>
          <div className="alert-body">{error}</div>
        </div>
      )}

      {/* Report type selection */}
      <div className="card">
        <div className="card-title">Report type</div>
        <div className="report-card-options">
          <label className={`report-type-card ${reportType === 'investigator' ? 'selected' : ''}`} htmlFor="rtype-investigator">
            <input id="rtype-investigator" type="radio" name="report_type" value="investigator" checked={reportType === 'investigator'} onChange={() => setReportType('investigator')} />
            <div className="report-type-name">Investigator summary</div>
            <div className="report-type-desc">Plain-language summary for officers. Approximately 3–5 pages. Suitable for briefings and court submissions.</div>
          </label>
          <label className={`report-type-card ${reportType === 'forensic' ? 'selected' : ''}`} htmlFor="rtype-forensic">
            <input id="rtype-forensic" type="radio" name="report_type" value="forensic" checked={reportType === 'forensic'} onChange={() => setReportType('forensic')} />
            <div className="report-type-name">Full forensic report</div>
            <div className="report-type-desc">Complete technical report with all appendices. Suitable for expert review and formal disclosure.</div>
          </label>
        </div>

        <div className="card-title" style={{ marginTop: '8px' }}>Report checklist</div>
        <ul className="checklist">
          {checklist.map((item, i) => (
            <ChecklistItem key={i} ok={item.ok} label={item.label} />
          ))}
        </ul>
      </div>

      {/* Examiner declaration */}
      <div className="card">
        <div className="card-title">Examiner declaration</div>
        <p style={{ fontSize: '14px', color: 'var(--color-text-secondary)', marginBottom: '16px' }}>
          These details appear in the report and are required for the full forensic report.
        </p>
        <div className="form-grid">
          <div className="form-group">
            <label className="form-label" htmlFor="decl-name">Full name</label>
            <input id="decl-name" className="form-control" value={declaration.name} onChange={e => setDeclaration(d => ({ ...d, name: e.target.value }))} />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="decl-rank">Rank and badge number</label>
            <input id="decl-rank" className="form-control" value={declaration.rank} onChange={e => setDeclaration(d => ({ ...d, rank: e.target.value }))} />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="decl-date">Date</label>
            <input id="decl-date" type="date" className="form-control" value={declaration.date} onChange={e => setDeclaration(d => ({ ...d, date: e.target.value }))} />
          </div>
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="decl-stmt">Declaration statement</label>
          <input id="decl-stmt" className="form-control" value={declaration.statement} readOnly style={{ background: 'var(--color-grey-100)' }} />
          <p className="form-hint">This statement is fixed and will appear in the report as written.</p>
        </div>
      </div>

      {/* Preview */}
      <div className="card">
        <div className="card-title">Report preview</div>
        <button
          type="button"
          id="btn-preview-report"
          className="btn btn--secondary"
          onClick={loadPreview}
          disabled={loadingPreview}
          style={{ marginBottom: '16px' }}
        >
          {loadingPreview ? (
            <><span className="spinner" style={{ width: 16, height: 16 }} /> Loading preview…</>
          ) : 'Load preview'}
        </button>
        {previewData && <ReportPreview data={previewData} />}
        {!previewData && !loadingPreview && (
          <p style={{ fontSize: '14px', color: 'var(--color-text-secondary)' }}>
            Click "Load preview" to see the report before downloading.
          </p>
        )}
      </div>

      {/* Download buttons */}
      <div className="card">
        <div className="card-title">Download report</div>
        <div className="btn-row">
          <button
            type="button"
            id="btn-download-docx"
            className="btn btn--primary"
            onClick={downloadDocx}
            disabled={downloadingDocx || !state.scanId}
          >
            {downloadingDocx ? (
              <><span className="spinner" style={{ width: 16, height: 16 }} /> Preparing…</>
            ) : 'Download Word document (.docx)'}
          </button>
          <button
            type="button"
            id="btn-download-json"
            className="btn btn--secondary"
            onClick={downloadJson}
            disabled={downloadingJson || !state.scanId}
          >
            {downloadingJson ? 'Exporting…' : 'Data export (.json) for specialists'}
          </button>
        </div>
        <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginTop: '12px' }}>
          PDF export: Convert the Word document using LibreOffice or Microsoft Word.
        </p>
      </div>
    </div>
  );
}
