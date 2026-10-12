/**
 * Step 3 – Analysis
 * Shows the 4-phase forensic pipeline with plain-language progress.
 * Uses SSE stream for live updates.
 */
import { useEffect, useRef, useState } from 'react';
import { useWorkbench } from '../context/WorkbenchContext';
import api from '../lib/api';
import { friendlyError } from '../lib/glossary';

const PHASES = [
  { key: 'checking',   label: 'Checking the evidence copy',    hint: 'Recording the digital fingerprint of the evidence file.' },
  { key: 'reading_fs', label: 'Reading the file system',        hint: 'Opening the EXT4 file system in read-only mode.' },
  { key: 'searching',  label: 'Looking for deleted files',      hint: 'Searching file records and directory entries for deleted items.' },
  { key: 'integrity',  label: 'Final integrity check',          hint: 'Verifying the evidence fingerprint is unchanged after analysis.' },
];

function phaseIndexFromStage(stage) {
  if (!stage) return -1;
  const map = {
    'Checking the evidence copy': 0,
    'Reading the file system': 1,
    'Looking for deleted files': 2,
    'Final integrity check': 3,
  };
  return map[stage] ?? -1;
}

export default function Analysis() {
  const { state, dispatch } = useWorkbench();
  const [scanState, setScanState] = useState({ status: null, stage: null, stage_index: 0, stage_total: 4, integrity_ok: null });
  const [error, setError] = useState(null);
  const [showTechnical, setShowTechnical] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const eventSourceRef = useRef(null);
  const scanStartedRef = useRef(false);

  useEffect(() => {
    if (scanStartedRef.current) return;
    scanStartedRef.current = true;

    async function startAndStream() {
      setError(null);
      // If we already have a complete scan from a refresh, jump directly
      if (state.scanId && state.scanStatus === 'complete') {
        await loadCandidatesAndAdvance(state.scanId);
        return;
      }

      try {
        let scanId = state.scanId;
        if (!scanId) {
          const scan = await api.startScan({
            case_id: state.caseId,
            evidence_path: state.evidencePath,
            report_profile: state.reportProfile || 'general',
          });
          scanId = scan.id;
          dispatch({ type: 'SET_SCAN', payload: scan });
        }
        startSSE(scanId);
      } catch (err) {
        const { friendly, action } = friendlyError(err);
        setError(`${friendly} ${action}`);
      }
    }

    startAndStream();
    return () => {
      if (eventSourceRef.current) eventSourceRef.current.close();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function startSSE(scanId) {
    const es = new EventSource(`/api/scans/${scanId}/stream`);
    eventSourceRef.current = es;

    es.onmessage = async (e) => {
      const data = JSON.parse(e.data);
      setScanState(data);
      dispatch({ type: 'SET_SCAN_STATUS', payload: data.status });

      if (data.done) {
        es.close();
        if (data.status === 'complete') {
          await loadCandidatesAndAdvance(scanId);
        } else if (data.status === 'failed') {
          setError(data.error_message || 'Analysis failed. Please try again.');
        }
      }
    };

    es.onerror = () => {
      es.close();
      // Fall back to polling
      pollUntilDone(scanId);
    };
  }

  function pollUntilDone(scanId) {
    const interval = setInterval(async () => {
      try {
        const scan = await api.getScan(scanId);
        setScanState({ status: scan.status, stage: scan.stage, stage_index: scan.stage_index, stage_total: scan.stage_total, integrity_ok: scan.integrity_ok });
        dispatch({ type: 'SET_SCAN_STATUS', payload: scan.status });
        if (scan.status === 'complete') {
          clearInterval(interval);
          await loadCandidatesAndAdvance(scanId);
        } else if (scan.status === 'failed' || scan.status === 'cancelled') {
          clearInterval(interval);
          setError(scan.error_message || `Analysis ${scan.status}.`);
        }
      } catch {}
    }, 2000);
  }

  async function loadCandidatesAndAdvance(scanId) {
    try {
      const result = await api.getCandidates(scanId);
      dispatch({ type: 'SET_CANDIDATES', payload: result.candidates || [] });
      dispatch({ type: 'SET_SCAN_RESULT', payload: result });

      // Refresh final scan state for integrity info
      const scan = await api.getScan(scanId);
      setScanState(s => ({ ...s, integrity_ok: scan.integrity_ok, status: scan.status }));
    } catch {}
  }

  async function handleCancel() {
    if (!state.scanId) return;
    setCancelling(true);
    try {
      await api.cancelScan(state.scanId);
    } catch {}
    setCancelling(false);
  }

  function handleContinue() {
    dispatch({ type: 'COMPLETE_STEP', payload: 3 });
    dispatch({ type: 'SET_STEP', payload: 4 });
  }

  function handleRetry() {
    dispatch({ type: 'SET_SCAN', payload: { id: null, status: null } });
    dispatch({ type: 'SET_STEP', payload: 2 });
  }

  const isDone = scanState.status === 'complete';
  const isFailed = scanState.status === 'failed' || scanState.status === 'cancelled';
  const isRunning = scanState.status === 'running' || scanState.status === 'pending';
  const progressPct = isDone ? 100 : Math.round((scanState.stage_index / (scanState.stage_total || 4)) * 100);
  const currentPhaseIdx = phaseIndexFromStage(scanState.stage);
  const integrityFailed = scanState.integrity_ok === false;

  return (
    <div>
      <div className="page-header">
        <div className="page-header-step">Step 3 of 6</div>
        <h1>Analysis in progress</h1>
        <p className="page-header-description">
          The evidence image is being analysed for deleted files.
          The original evidence file is opened read-only and will not be changed.
        </p>
      </div>

      {integrityFailed && (
        <div className="integrity-failure" role="alert" aria-atomic="true">
          <div className="integrity-failure-title">⚠ Evidence file changed during analysis</div>
          <div className="integrity-failure-body">
            <p>The digital fingerprint of the evidence file was different before and after analysis.
            This is a serious concern. <strong>Do not rely on these results.</strong></p>
            <p style={{ marginTop: '8px' }}>Contact your supervisor before proceeding.</p>
          </div>
        </div>
      )}

      {error && !integrityFailed && (
        <div className="alert alert--danger" role="alert">
          <span className="alert-icon">⚠</span>
          <div className="alert-body">
            <div className="alert-title">Analysis stopped</div>
            <div>{error}</div>
          </div>
        </div>
      )}

      <div className="card">
        <div className="progress-section">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontWeight: 600, fontSize: '15px' }}>
              {isDone ? 'Analysis complete' : isFailed ? 'Analysis stopped' : scanState.stage || 'Starting…'}
            </span>
            <span style={{ fontSize: '13px', color: 'var(--color-text-secondary)' }} aria-live="polite" aria-label={`Progress: ${progressPct} percent`}>
              {progressPct}%
            </span>
          </div>
          <div className="progress-bar-track" role="progressbar" aria-valuenow={progressPct} aria-valuemin="0" aria-valuemax="100">
            <div className="progress-bar-fill" style={{ width: `${progressPct}%` }} />
          </div>

          <div className="progress-phases">
            {PHASES.map((phase, i) => {
              let cls = 'phase-item';
              if (i < currentPhaseIdx || isDone) cls += ' done';
              else if (i === currentPhaseIdx && !isDone) cls += ' active';
              return (
                <div key={phase.key} className={cls} title={phase.hint}>
                  {i < currentPhaseIdx || isDone ? '✓ ' : ''}{phase.label}
                </div>
              );
            })}
          </div>
        </div>

        {isRunning && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '16px', fontSize: '14px', color: 'var(--color-text-secondary)' }}>
            <span className="spinner" aria-hidden="true" />
            <span aria-live="polite">Please wait. The original evidence is open read-only and is not being changed.</span>
          </div>
        )}

        {isDone && !integrityFailed && (
          <div className="alert alert--success" style={{ marginTop: '16px' }}>
            <span className="alert-icon">✓</span>
            <div className="alert-body">
              <div className="alert-title">Analysis complete. Evidence unchanged.</div>
              <div>The digital fingerprint of the evidence was the same before and after analysis.</div>
            </div>
          </div>
        )}
      </div>

      <details className="disclosure">
        <summary className="disclosure-summary" onClick={() => setShowTechnical(s => !s)}>
          ▶ Technical details for advanced users
        </summary>
        <div className="disclosure-content">
          <div><strong>Scan ID:</strong> {state.scanId}</div>
          <div><strong>Status:</strong> {scanState.status}</div>
          <div><strong>Stage:</strong> {scanState.stage}</div>
          <div><strong>Evidence path:</strong> <span className="mono-value">{state.evidencePath}</span></div>
        </div>
      </details>

      <div className="btn-row">
        {isRunning && !cancelling && (
          <button type="button" className="btn btn--secondary" onClick={handleCancel}>
            Cancel analysis
          </button>
        )}
        {isRunning && cancelling && (
          <span style={{ fontSize: '14px', color: 'var(--color-text-secondary)' }}>Cancelling – the evidence has not been changed.</span>
        )}
        {isFailed && (
          <button type="button" className="btn btn--secondary" onClick={handleRetry}>
            ← Go back and try again
          </button>
        )}
        {isDone && !integrityFailed && (
          <button
            type="button"
            id="btn-review-files"
            className="btn btn--primary btn--lg"
            onClick={handleContinue}
          >
            Review deleted files →
          </button>
        )}
        {isDone && integrityFailed && (
          <button type="button" className="btn btn--secondary" onClick={handleRetry}>
            ← Start over
          </button>
        )}
      </div>
      {isDone && !integrityFailed && (
        <p className="btn-next-hint">Next: Review the list of deleted files found.</p>
      )}
    </div>
  );
}
