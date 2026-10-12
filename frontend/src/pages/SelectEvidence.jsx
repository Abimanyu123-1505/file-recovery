/**
 * Step 2 – Select Evidence
 * Lets the officer choose an evidence image with a path check before proceeding.
 */
import { useEffect, useState } from 'react';
import { useWorkbench } from '../context/WorkbenchContext';
import api from '../lib/api';
import { formatSize, friendlyError } from '../lib/glossary';

export default function SelectEvidence() {
  const { state, dispatch } = useWorkbench();
  const [path, setPath] = useState(state.evidencePath || '');
  const [checking, setChecking] = useState(false);
  const [checkResult, setCheckResult] = useState(state.evidenceCheck || null);
  const [listedFiles, setListedFiles] = useState([]);
  const [showHelp, setShowHelp] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.listEvidence()
      .then(r => setListedFiles(r.files || []))
      .catch(() => {});
  }, []);

  async function handleCheck() {
    if (!path.trim()) {
      setError('Please enter a file path.');
      return;
    }
    setChecking(true);
    setError(null);
    setCheckResult(null);
    try {
      const result = await api.checkEvidence(path.trim());
      setCheckResult(result);
      dispatch({ type: 'SET_EVIDENCE_CHECK', payload: result });
      dispatch({ type: 'SET_EVIDENCE_PATH', payload: path.trim() });
    } catch (err) {
      const { friendly } = friendlyError(err);
      setError(friendly);
    } finally {
      setChecking(false);
    }
  }

  function handleSelectListed(filePath) {
    setPath(filePath);
    setCheckResult(null);
    dispatch({ type: 'SET_EVIDENCE_PATH', payload: filePath });
  }

  function handleSelectRecent(recentPath) {
    setPath(recentPath);
    setCheckResult(null);
    dispatch({ type: 'SET_EVIDENCE_PATH', payload: recentPath });
  }

  async function handleContinue() {
    if (!checkResult?.looks_like_ext4) return;
    dispatch({ type: 'SET_EVIDENCE_PATH', payload: path.trim() });
    dispatch({ type: 'ADD_RECENT_PATH', payload: path.trim() });
    dispatch({ type: 'COMPLETE_STEP', payload: 2 });
    dispatch({ type: 'SET_STEP', payload: 3 });
  }

  const checkOk = checkResult?.looks_like_ext4 === true;
  const checkFailed = checkResult && !checkOk;

  return (
    <div>
      <div className="page-header">
        <div className="page-header-step">Step 2 of 6</div>
        <h1>Select the evidence image</h1>
        <p className="page-header-description">
          An <strong>evidence image</strong> is a complete, exact copy of a storage device's
          contents, saved as a single file. Enter the file path below and click
          "Check file" to verify it before analysis begins.
        </p>
      </div>

      <div className="card">
        <div className="card-title">Evidence file path</div>

        <div className="path-input-row">
          <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
            <label className="form-label" htmlFor="evidence-path">
              Full path to the evidence image file
            </label>
            <input
              id="evidence-path"
              className="form-control form-control--mono"
              value={path}
              onChange={e => { setPath(e.target.value); setCheckResult(null); setError(null); }}
              placeholder="e.g. C:\Evidence\case-0142\disk.img"
              onKeyDown={e => e.key === 'Enter' && handleCheck()}
              aria-describedby="path-hint"
            />
            <p className="form-hint" id="path-hint">
              Supported formats: .img, .dd, .raw, .bin, .e01
            </p>
          </div>
          <div style={{ marginTop: '22px' }}>
            <button
              type="button"
              id="btn-check-file"
              className="btn btn--secondary"
              onClick={handleCheck}
              disabled={checking || !path.trim()}
            >
              {checking ? (
                <><span className="spinner" style={{width:16,height:16}} /> Checking...</>
              ) : 'Check file'}
            </button>
          </div>
        </div>

        <div style={{ marginTop: '12px' }}>
          <button
            type="button"
            className="btn btn--secondary btn--sm"
            onClick={() => setShowHelp(h => !h)}
            aria-expanded={showHelp}
          >
            {showHelp ? 'Hide help' : 'How do I find the file path?'}
          </button>
          {showHelp && (
            <div className="alert alert--info" style={{ marginTop: '12px' }}>
              <span className="alert-icon">ℹ</span>
              <div className="alert-body">
                <div className="alert-title">Finding the file path</div>
                <p style={{ marginBottom: '8px' }}>
                  <strong>Windows:</strong> Hold <kbd>Shift</kbd> and right-click the file in
                  File Explorer. Choose "Copy as path". Then paste it here.
                </p>
                <p>
                  <strong>Linux/Mac:</strong> Open a terminal, navigate to the file's folder,
                  and type <code>pwd</code> to see the folder path, then add the filename.
                </p>
              </div>
            </div>
          )}
        </div>

        {error && (
          <div className="alert alert--danger" style={{ marginTop: '16px' }} role="alert">
            <span className="alert-icon">⚠</span>
            <div className="alert-body">{error}</div>
          </div>
        )}

        {checkResult && (
          <div
            className={`alert ${checkOk ? 'alert--success' : 'alert--danger'}`}
            style={{ marginTop: '16px' }}
            role="status"
            aria-live="polite"
          >
            <span className="alert-icon">{checkOk ? '✓' : '✕'}</span>
            <div className="alert-body">
              <div className="alert-title">{checkOk ? 'File check passed' : 'File check failed'}</div>
              <div>{checkResult.friendly_description}</div>
              {checkResult.size && (
                <div style={{ marginTop: '4px', fontSize: '13px' }}>
                  Size: {formatSize(checkResult.size)}
                </div>
              )}
              {checkFailed && checkResult.error && (
                <div style={{ marginTop: '4px', fontSize: '13px', fontFamily: 'var(--font-mono)' }}>
                  Technical detail: {checkResult.error}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-title">Processing &amp; CPU Management</div>
        <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginBottom: '12px' }}>
          Select the performance preset suitable for your triage device.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '12px' }}>
          <button
            type="button"
            className={`btn ${state.cpuProfile === 'laptop' ? 'btn--primary' : 'btn--secondary'}`}
            style={{ textAlign: 'left', padding: '12px', height: 'auto', display: 'flex', flexDirection: 'column' }}
            onClick={() => dispatch({ type: 'SET_CPU_PROFILE', payload: 'laptop' })}
          >
            <div style={{ fontWeight: 600 }}>Field / Laptop (Conservative)</div>
            <div style={{ fontSize: '12px', opacity: 0.85, marginTop: '4px' }}>
              Gentle pacing, low thermal footprint, and battery preservation for field laptops.
            </div>
          </button>
          <button
            type="button"
            className={`btn ${state.cpuProfile === 'desktop' ? 'btn--primary' : 'btn--secondary'}`}
            style={{ textAlign: 'left', padding: '12px', height: 'auto', display: 'flex', flexDirection: 'column' }}
            onClick={() => dispatch({ type: 'SET_CPU_PROFILE', payload: 'desktop' })}
          >
            <div style={{ fontWeight: 600 }}>Lab / Workstation (High Throughput)</div>
            <div style={{ fontSize: '12px', opacity: 0.85, marginTop: '4px' }}>
              Unconstrained multi-core processing for dedicated forensic lab workstations.
            </div>
          </button>
        </div>
      </div>

      {listedFiles.length > 0 && (
        <div className="card">
          <div className="card-title">Available evidence images</div>
          <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginBottom: '12px' }}>
            These files are in the configured evidence folder.
          </p>
          <ul className="recent-file-list">
            {listedFiles.map(f => (
              <li key={f.path}>
                <button
                  type="button"
                  className="recent-file-item"
                  style={{ width: '100%', cursor: 'pointer' }}
                  onClick={() => handleSelectListed(f.path)}
                >
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '13px' }}>
                    {f.name}
                  </span>
                  <span style={{ marginLeft: 'auto', fontSize: '12px', color: 'var(--color-text-secondary)' }}>
                    {formatSize(f.size)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {state.recentPaths.length > 0 && (
        <div className="card">
          <div className="card-title">Recently used</div>
          <ul className="recent-file-list">
            {state.recentPaths.map(p => (
              <li key={p}>
                <button
                  type="button"
                  className="recent-file-item"
                  style={{ width: '100%' }}
                  onClick={() => handleSelectRecent(p)}
                >
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '13px' }}>{p}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="btn-row">
        <button
          type="button"
          className="btn btn--secondary"
          onClick={() => dispatch({ type: 'SET_STEP', payload: 1 })}
        >
          ← Back
        </button>
        <button
          type="button"
          id="btn-start-analysis"
          className="btn btn--primary btn--lg"
          onClick={handleContinue}
          disabled={!checkOk}
          aria-disabled={!checkOk}
        >
          Start analysis →
        </button>
      </div>
      {!checkOk && (
        <p className="btn-next-hint">Check the file first – "Start analysis" will be enabled when the check passes.</p>
      )}
      {checkOk && (
        <p className="btn-next-hint">Next: The evidence image will be analysed for deleted files.</p>
      )}
    </div>
  );
}
