/**
 * Step 5 – Recover
 * Confirm panel → recovery request → per-file results with fingerprints.
 */
import { useState } from 'react';
import { useWorkbench } from '../context/WorkbenchContext';
import api from '../lib/api';
import { formatSize, friendlyError } from '../lib/glossary';
import ConfirmDialog from '../components/ConfirmDialog';
import CopyButton from '../components/CopyButton';

function StatusBadge({ status }) {
  const map = {
    FULL: { cls: 'badge--success', label: 'Fully recovered' },
    PARTIAL: { cls: 'badge--caution', label: 'Partly recovered – some data is missing' },
    FAILED: { cls: 'badge--danger', label: 'Could not be recovered' },
  };
  const info = map[status] || { cls: 'badge--neutral', label: status || 'Unknown' };
  return <span className={`badge ${info.cls}`}>{info.label}</span>;
}

export default function Recover() {
  const { state, dispatch } = useWorkbench();
  const candidates = state.candidates || [];
  const selectedInodes = state.selectedInodes || [];

  const selectedFiles = candidates.filter(c => selectedInodes.includes(c.inode));

  const [showConfirm, setShowConfirm] = useState(false);
  const [recovering, setRecovering] = useState(false);
  const [results, setResults] = useState(state.recoveries || []);
  const [error, setError] = useState(null);

  const isDone = results.length > 0;

  async function handleRecover() {
    setShowConfirm(false);
    setRecovering(true);
    setError(null);
    try {
      const res = await api.recover({
        scan_id: state.scanId,
        inodes: selectedInodes,
      });
      const recList = res.results || [];
      setResults(recList);
      dispatch({ type: 'SET_RECOVERIES', payload: recList });
    } catch (err) {
      const { friendly, action } = friendlyError(err);
      setError(`${friendly} ${action}`);
    } finally {
      setRecovering(false);
    }
  }

  function handleContinue() {
    dispatch({ type: 'COMPLETE_STEP', payload: 5 });
    dispatch({ type: 'SET_STEP', payload: 6 });
  }

  const outputDir = `case/scan_${state.scanId}/recovered`;
  const sha256Set = new Map();
  results.forEach(r => {
    if (r.sha256) {
      if (!sha256Set.has(r.sha256)) sha256Set.set(r.sha256, r.inode);
    }
  });

  return (
    <div>
      <div className="page-header">
        <div className="page-header-step">Step 5 of 6</div>
        <h1>Recover files</h1>
        <p className="page-header-description">
          Review what will be recovered. Copies of the selected files will be saved
          to a separate output folder. The original evidence is not changed.
        </p>
      </div>

      {!isDone && (
        <>
          <div className="card">
            <div className="card-title">Files to be recovered ({selectedFiles.length})</div>
            <div className="alert alert--info" style={{ marginBottom: '16px' }}>
              <span className="alert-icon">ℹ</span>
              <div className="alert-body">
                Copies will be saved to: <span className="mono-value">{outputDir}</span>
                <br />The original evidence file will not be altered.
              </div>
            </div>
            <div className="table-wrapper">
              <table aria-label="Files to recover">
                <thead>
                  <tr>
                    <th>File name</th>
                    <th>Where it was stored</th>
                    <th>Size</th>
                    <th>Type</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedFiles.map(f => (
                    <tr key={f.inode}>
                      <td>{f.name || <em>(name not available)</em>}</td>
                      <td>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
                          {f.path || <em style={{ fontFamily: 'var(--font-sans)' }}>(not available)</em>}
                        </span>
                      </td>
                      <td>{formatSize(f.size)}</td>
                      <td>{f.friendly_type || f.file_type}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {error && (
            <div className="alert alert--danger" role="alert">
              <span className="alert-icon">⚠</span>
              <div className="alert-body">
                <div className="alert-title">Recovery failed</div>
                <div>{error}</div>
              </div>
            </div>
          )}

          <div className="btn-row">
            <button type="button" className="btn btn--secondary" onClick={() => dispatch({ type: 'SET_STEP', payload: 4 })}>
              ← Back
            </button>
            <button
              type="button"
              id="btn-start-recovery"
              className="btn btn--primary btn--lg"
              onClick={() => setShowConfirm(true)}
              disabled={recovering || selectedFiles.length === 0}
            >
              {recovering ? (
                <><span className="spinner" style={{ width: 16, height: 16 }} /> Recovering…</>
              ) : 'Start recovery'}
            </button>
          </div>
          <p className="btn-next-hint">Next: View recovery results and download a report.</p>
        </>
      )}

      {isDone && (
        <>
          <div className="stat-row">
            <div className="stat-card">
              <div className="stat-number" style={{ color: 'var(--color-success)' }}>
                {results.filter(r => r.status === 'FULL').length}
              </div>
              <div className="stat-label">Fully recovered</div>
            </div>
            <div className="stat-card">
              <div className="stat-number" style={{ color: 'var(--color-caution)' }}>
                {results.filter(r => r.status === 'PARTIAL').length}
              </div>
              <div className="stat-label">Partly recovered</div>
            </div>
            <div className="stat-card">
              <div className="stat-number" style={{ color: 'var(--color-danger)' }}>
                {results.filter(r => r.status === 'FAILED' || r.error).length}
              </div>
              <div className="stat-label">Not recovered</div>
            </div>
          </div>

          <div className="card">
            <div className="card-title">Recovery results</div>
            <div className="table-wrapper">
              <table aria-label="Recovery results">
                <thead>
                  <tr>
                    <th>Exhibit</th>
                    <th>File name</th>
                    <th>Status</th>
                    <th>Digital fingerprint (SHA-256)</th>
                    <th>Size recovered</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((r, i) => {
                    const isDuplicate = r.sha256 && sha256Set.get(r.sha256) !== r.inode;
                    return (
                      <tr key={r.inode || i}>
                        <td><span className="badge badge--info">{r.exhibit_number || '–'}</span></td>
                        <td>
                          <div>{r.file_name || <em>(name not available)</em>}</div>
                          <div style={{ fontSize: '11px', color: 'var(--color-text-secondary)', fontFamily: 'var(--font-mono)' }}>
                            {r.inode ? `File record: ${r.inode}` : ''}
                          </div>
                        </td>
                        <td>
                          {r.error
                            ? <span className="badge badge--danger">Could not be recovered</span>
                            : <StatusBadge status={r.status} />}
                          {isDuplicate && (
                            <div className="badge badge--caution" style={{ marginTop: '4px', display: 'block' }}>
                              Same fingerprint as another finding
                            </div>
                          )}
                        </td>
                        <td>
                          {r.sha256 ? (
                            <div className="copy-row">
                              <span className="mono-value" style={{ fontSize: '11px' }}>
                                {r.sha256.slice(0, 16)}…
                              </span>
                              <CopyButton text={r.sha256} label="fingerprint" />
                            </div>
                          ) : '–'}
                        </td>
                        <td>{formatSize(r.size_bytes)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginTop: '12px' }}>
              Recovered files are saved to: <span className="mono-value">{outputDir}</span>
            </p>
          </div>

          <div className="btn-row btn-row--right">
            <button
              type="button"
              id="btn-to-report"
              className="btn btn--primary btn--lg"
              onClick={handleContinue}
            >
              Generate report →
            </button>
          </div>
          <p className="btn-next-hint">Next: Build and download the case report.</p>
        </>
      )}

      {showConfirm && (
        <ConfirmDialog
          title="Confirm file recovery"
          message={`${selectedFiles.length} file${selectedFiles.length !== 1 ? 's' : ''} will be copied to the output folder. This action cannot be undone. The original evidence will not be changed.`}
          confirmLabel="Yes, recover files"
          cancelLabel="Go back"
          onConfirm={handleRecover}
          onCancel={() => setShowConfirm(false)}
        />
      )}
    </div>
  );
}
