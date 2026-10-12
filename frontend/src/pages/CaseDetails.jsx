/**
 * Step 1 – Case Details
 * Collects all case metadata before analysis begins.
 */
import { useState } from 'react';
import { useWorkbench } from '../context/WorkbenchContext';
import api from '../lib/api';
import { friendlyError } from '../lib/glossary';

export default function CaseDetails() {
  const { state, dispatch } = useWorkbench();

  const [form, setForm] = useState({
    case_number: state.caseData?.case_number || '',
    case_title: state.caseData?.case_title || '',
    examiner_name: state.caseData?.examiner_name || '',
    rank_badge: state.caseData?.rank_badge || '',
    department: state.caseData?.department || '',
    requesting_authority: state.caseData?.requesting_authority || '',
    date_received: state.caseData?.date_received || '',
    notes: state.caseData?.notes || '',
  });

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  function handleChange(e) {
    const { name, value } = e.target;
    setForm(f => ({ ...f, [name]: value }));
    setError(null);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!form.case_number.trim()) {
      setError('Case number is required.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      let caseData;
      if (state.caseId) {
        caseData = await api.updateCase(state.caseId, form);
      } else {
        caseData = await api.createCase(form);
      }
      dispatch({ type: 'SET_CASE', payload: caseData });
      dispatch({ type: 'COMPLETE_STEP', payload: 1 });
      dispatch({ type: 'SET_STEP', payload: 2 });
    } catch (err) {
      const { friendly, action } = friendlyError(err);
      setError(`${friendly} ${action}`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <div className="page-header-step">Step 1 of 6</div>
        <h1>Case Details</h1>
        <p className="page-header-description">
          Enter the details for this case. This information will appear on all reports.
          The case number is required; all other fields are recommended.
        </p>
      </div>

      {error && (
        <div className="alert alert--danger" role="alert">
          <span className="alert-icon">⚠</span>
          <div className="alert-body">
            <div className="alert-title">Could not save case details</div>
            <div>{error}</div>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} noValidate>
        <div className="card">
          <div className="card-title">Case identification</div>
          <div className="form-grid">
            <div className="form-group">
              <label className="form-label form-label-required" htmlFor="case_number">
                Case number
              </label>
              <input
                id="case_number"
                name="case_number"
                className="form-control"
                value={form.case_number}
                onChange={handleChange}
                placeholder="e.g. CID/2026/00142"
                required
                aria-required="true"
                autoComplete="off"
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="case_title">Case title</label>
              <input
                id="case_title"
                name="case_title"
                className="form-control"
                value={form.case_title}
                onChange={handleChange}
                placeholder="Brief description of the case"
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="requesting_authority">
                Requesting authority or warrant/reference number
              </label>
              <input
                id="requesting_authority"
                name="requesting_authority"
                className="form-control"
                value={form.requesting_authority}
                onChange={handleChange}
                placeholder="e.g. Crown Court Order CR-2026-0041"
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="date_received">
                Date evidence received
              </label>
              <input
                id="date_received"
                name="date_received"
                type="date"
                className="form-control"
                value={form.date_received}
                onChange={handleChange}
              />
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-title">Examiner details</div>
          <div className="form-grid">
            <div className="form-group">
              <label className="form-label" htmlFor="examiner_name">Examiner name</label>
              <input
                id="examiner_name"
                name="examiner_name"
                className="form-control"
                value={form.examiner_name}
                onChange={handleChange}
                placeholder="Full name"
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="rank_badge">Rank and badge number</label>
              <input
                id="rank_badge"
                name="rank_badge"
                className="form-control"
                value={form.rank_badge}
                onChange={handleChange}
                placeholder="e.g. Detective Constable / Badge 4821"
              />
            </div>
            <div className="form-group" style={{ gridColumn: '1 / -1' }}>
              <label className="form-label" htmlFor="department">Department / Unit</label>
              <input
                id="department"
                name="department"
                className="form-control"
                value={form.department}
                onChange={handleChange}
                placeholder="e.g. Digital Forensics Unit, Metropolitan Police"
              />
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-title">Additional notes</div>
          <div className="form-group">
            <label className="form-label" htmlFor="notes">Notes</label>
            <textarea
              id="notes"
              name="notes"
              className="form-control"
              value={form.notes}
              onChange={handleChange}
              rows={3}
              placeholder="Any relevant context for this examination"
            />
          </div>
        </div>

        <div className="btn-row btn-row--right">
          <button
            type="submit"
            className="btn btn--primary btn--lg"
            id="btn-save-case"
            disabled={saving}
          >
            {saving ? 'Saving...' : 'Save and continue'}
          </button>
        </div>
        <p className="btn-next-hint">Next: Select the evidence image file</p>
      </form>
    </div>
  );
}
