/**
 * HelpDrawer – slides in from the right with quick-start guide and glossary.
 */
import { TERMS } from '../lib/glossary';

export default function HelpDrawer({ onClose }) {
  return (
    <>
      <div className="drawer-overlay" onClick={onClose} aria-hidden="true" />
      <div className="drawer" role="dialog" aria-modal="true" aria-labelledby="help-drawer-title">
        <div className="drawer-header">
          <h2 className="drawer-title" id="help-drawer-title">Help &amp; Quick Start</h2>
          <button type="button" className="drawer-close" onClick={onClose} aria-label="Close help">
            ✕
          </button>
        </div>
        <div className="drawer-body">
          <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '12px' }}>Quick start (6 steps)</h3>
          <ol style={{ paddingLeft: '20px', lineHeight: 1.8, fontSize: '14px', marginBottom: '24px' }}>
            <li>Enter the case details (case number is required).</li>
            <li>Enter the path to the evidence image file and check it.</li>
            <li>Start the analysis and wait for it to complete.</li>
            <li>Review the list of deleted files found. Select files to recover.</li>
            <li>Confirm recovery. Files are saved to a separate output folder.</li>
            <li>Choose a report type, complete the examiner declaration, and download.</li>
          </ol>

          <div style={{ padding: '12px 16px', background: 'var(--color-info-bg)', border: '1px solid var(--color-info-border)', borderRadius: '6px', fontSize: '13px', marginBottom: '24px', color: 'var(--color-info)' }}>
            <strong>Important:</strong> The original evidence file is opened read-only and is never changed or written to.
          </div>

          <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '12px' }}>Glossary of terms</h3>
          <dl style={{ fontSize: '13px', lineHeight: 1.6 }}>
            {Object.entries(TERMS).map(([key, val]) => (
              <div key={key} style={{ marginBottom: '12px' }}>
                <dt style={{ fontWeight: 600, color: 'var(--color-text)' }}>{val.plain}</dt>
                <dd style={{ color: 'var(--color-text-secondary)', marginLeft: '0' }}>{val.tooltip}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </>
  );
}
