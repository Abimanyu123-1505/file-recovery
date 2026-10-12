/**
 * Step 4 – Review Deleted Files
 * Shows the list of deleted files with filtering, search, name confidence labels, and selection.
 */
import { useMemo, useState } from 'react';
import { useWorkbench } from '../context/WorkbenchContext';
import { NAME_CONFIDENCE, formatSize } from '../lib/glossary';
import CopyButton from '../components/CopyButton';
import Tooltip from '../components/Tooltip';

const FILTER_CATEGORIES = ['All', 'Documents', 'Archives', 'Images', 'Other'];

function matchCategory(candidate, cat) {
  const name = candidate.name || '';
  const ext = name.split('.').pop()?.toLowerCase() || '';
  if (cat === 'All') return true;
  const docs = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'csv', 'rtf', 'odt', 'ods'];
  const archives = ['zip', 'gz', 'tar', 'rar', '7z', 'bz2', 'xz', 'zst'];
  const images = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tif', 'tiff', 'svg', 'webp'];
  if (cat === 'Documents') return docs.includes(ext);
  if (cat === 'Archives') return archives.includes(ext);
  if (cat === 'Images') return images.includes(ext);
  return !docs.includes(ext) && !archives.includes(ext) && !images.includes(ext);
}

function NameConfidenceBadge({ confidence }) {
  const info = NAME_CONFIDENCE[confidence] || NAME_CONFIDENCE.none;
  const badgeClass = {
    success: 'badge--success',
    caution: 'badge--caution',
    neutral: 'badge--neutral',
  }[info.badge] || 'badge--neutral';

  return (
    <Tooltip label={info.label} text={info.note}>
      <span className={`badge ${badgeClass}`}>{info.label}</span>
    </Tooltip>
  );
}

function RecoverBadge({ can }) {
  if (can) return <span className="badge badge--success">Yes</span>;
  return <span className="badge badge--neutral">Size unknown</span>;
}

export default function ReviewFiles() {
  const { state, dispatch } = useWorkbench();
  const candidates = state.candidates || [];

  const [filter, setFilter] = useState('All');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(
    () => new Set(state.selectedInodes || [])
  );

  const filtered = useMemo(() => {
    return candidates.filter(c => {
      const matchSearch = !search ||
        (c.name || '').toLowerCase().includes(search.toLowerCase()) ||
        (c.path || '').toLowerCase().includes(search.toLowerCase());
      return matchSearch && matchCategory(c, filter);
    });
  }, [candidates, filter, search]);

  const recoverableInTable = useMemo(() => filtered.filter(c => c.can_recover), [filtered]);

  function toggleOne(inode) {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(inode)) next.delete(inode);
      else next.add(inode);
      return next;
    });
  }

  function selectAllRecoverable() {
    setSelected(new Set(recoverableInTable.map(c => c.inode)));
  }

  function clearAll() {
    setSelected(new Set());
  }

  function handleContinue() {
    dispatch({ type: 'SET_SELECTED_INODES', payload: Array.from(selected) });
    dispatch({ type: 'COMPLETE_STEP', payload: 4 });
    dispatch({ type: 'SET_STEP', payload: 5 });
  }

  const totalRecoverable = candidates.filter(c => c.can_recover).length;

  return (
    <div>
      <div className="page-header">
        <div className="page-header-step">Step 4 of 6</div>
        <h1>Review deleted files</h1>
        <p className="page-header-description">
          {candidates.length === 0
            ? 'No deleted file records were found.'
            : `${candidates.length} deleted file record${candidates.length !== 1 ? 's were' : ' was'} found.`}
          {totalRecoverable > 0 && ` ${totalRecoverable} can be recovered.`}
        </p>
      </div>

      {candidates.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-title">No deleted files found</div>
          <p>The analysis did not find any deleted file records in this evidence image.</p>
        </div>
      ) : (
        <>
          <div className="stat-row">
            <div className="stat-card">
              <div className="stat-number">{candidates.length}</div>
              <div className="stat-label">Files found</div>
            </div>
            <div className="stat-card">
              <div className="stat-number">{totalRecoverable}</div>
              <div className="stat-label">Recoverable</div>
            </div>
            <div className="stat-card">
              <div className="stat-number">{candidates.filter(c => c.name_confidence === 'confirmed').length}</div>
              <div className="stat-label">Name confirmed</div>
            </div>
            <div className="stat-card">
              <div className="stat-number">{selected.size}</div>
              <div className="stat-label">Selected</div>
            </div>
          </div>

          <div className="card">
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap' }}>
              <div className="search-box" style={{ flex: 1, minWidth: '200px', marginBottom: 0 }}>
                <span className="search-box-icon" aria-hidden="true">⌕</span>
                <input
                  id="file-search"
                  type="search"
                  placeholder="Search by file name or path"
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  aria-label="Search files"
                />
              </div>
              <button type="button" className="btn btn--secondary btn--sm" onClick={selectAllRecoverable}>
                Select all recoverable
              </button>
              <button type="button" className="btn btn--secondary btn--sm" onClick={clearAll}>
                Clear selection
              </button>
            </div>

            <div className="filter-chips" role="group" aria-label="Filter by file type">
              {FILTER_CATEGORIES.map(cat => (
                <button
                  key={cat}
                  type="button"
                  className={`chip ${filter === cat ? 'active' : ''}`}
                  onClick={() => setFilter(cat)}
                  aria-pressed={filter === cat}
                >
                  {cat}
                </button>
              ))}
            </div>

            <div className="table-wrapper">
              <table aria-label="Deleted files found">
                <thead>
                  <tr>
                    <th style={{ width: 40 }}><span className="sr-only">Select</span></th>
                    <th>File name</th>
                    <th>Where it was stored</th>
                    <th>Size</th>
                    <th>Type</th>
                    <th>Name confidence</th>
                    <th>Can be recovered?</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.length === 0 ? (
                    <tr>
                      <td colSpan={7} style={{ textAlign: 'center', color: 'var(--color-text-secondary)', padding: '24px' }}>
                        No files match the current filter.
                      </td>
                    </tr>
                  ) : filtered.map(c => (
                    <tr key={c.inode}>
                      <td>
                        <label className="checkbox-label" htmlFor={`sel-${c.inode}`} style={{ justifyContent: 'center' }}>
                          <input
                            id={`sel-${c.inode}`}
                            type="checkbox"
                            checked={selected.has(c.inode)}
                            onChange={() => toggleOne(c.inode)}
                            disabled={!c.can_recover}
                            aria-label={`Select ${c.name || `file record ${c.inode}`}`}
                          />
                        </label>
                      </td>
                      <td>
                        <div style={{ fontWeight: c.name ? 600 : 400, color: c.name ? 'var(--color-text)' : 'var(--color-text-secondary)' }}>
                          {c.name || <em>(name not available)</em>}
                        </div>
                        <div style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--color-text-secondary)', marginTop: '2px' }}>
                          {c.inode ? `File record: ${c.inode}` : ''}
                        </div>
                      </td>
                      <td>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
                          {c.path || <em style={{ fontFamily: 'var(--font-sans)' }}>(not available)</em>}
                        </span>
                      </td>
                      <td style={{ whiteSpace: 'nowrap' }}>{formatSize(c.size)}</td>
                      <td>{c.friendly_type || c.file_type}</td>
                      <td>
                        <NameConfidenceBadge confidence={c.name_confidence} />
                      </td>
                      <td><RecoverBadge can={c.can_recover} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {filtered.length > 0 && (
              <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginTop: '8px' }}>
                Showing {filtered.length} of {candidates.length} files.
              </p>
            )}
          </div>

          <div className="alert alert--info">
            <span className="alert-icon">ℹ</span>
            <div className="alert-body">
              <strong>Name confidence explained:</strong>{' '}
              A "Name confirmed" label means the file name was found in a surviving directory record – the most reliable source.
              "Name uncertain" means the name was found in leftover data only and may not be the original name.
              Names labelled "not available" could not be recovered. Never treat uncertain names as confirmed facts.
            </div>
          </div>

          <div className="btn-row">
            <button type="button" className="btn btn--secondary" onClick={() => dispatch({ type: 'SET_STEP', payload: 3 })}>
              ← Back
            </button>
            <button
              type="button"
              id="btn-proceed-recovery"
              className="btn btn--primary btn--lg"
              onClick={handleContinue}
              disabled={selected.size === 0}
            >
              Recover {selected.size > 0 ? `${selected.size} file${selected.size !== 1 ? 's' : ''}` : 'selected files'} →
            </button>
          </div>
          {selected.size === 0 && (
            <p className="btn-next-hint">Select at least one file to continue.</p>
          )}
          {selected.size > 0 && (
            <p className="btn-next-hint">Next: Review and confirm what will be recovered.</p>
          )}
        </>
      )}
    </div>
  );
}
