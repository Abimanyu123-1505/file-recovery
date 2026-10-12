/**
 * API client – all backend communication goes through here.
 */

const BASE = '/api';

async function _request(method, path, body) {
  const opts = {
    method,
    headers: {},
  };
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      detail = err.detail || JSON.stringify(err);
    } catch {}
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

const api = {
  // Health
  health: () => _request('GET', '/health'),

  // Cases
  createCase: (data) => _request('POST', '/cases', data),
  listCases: () => _request('GET', '/cases'),
  getCase: (id) => _request('GET', `/cases/${id}`),
  updateCase: (id, data) => _request('PATCH', `/cases/${id}`, data),

  // Evidence
  checkEvidence: (path) => _request('GET', `/evidence/check?path=${encodeURIComponent(path)}`),
  listEvidence: () => _request('GET', '/evidence/list'),

  // Scans
  startScan: (data) => _request('POST', '/scans', data),
  getScan: (id) => _request('GET', `/scans/${id}`),
  getCandidates: (id) => _request('GET', `/scans/${id}/candidates`),
  cancelScan: (id) => _request('POST', `/scans/${id}/cancel`),
  getRecoveries: (id) => _request('GET', `/scans/${id}/recoveries`),

  // Recovery
  recover: (data) => _request('POST', '/recover', data),

  // Reports
  reportJson: (scanId, data) => _request('POST', `/reports/${scanId}/json`, data),
  reportDocx: async (scanId, data) => {
    const opts = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    };
    const res = await fetch(`${BASE}/reports/${scanId}/docx`, opts);
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const err = await res.json();
        detail = err.detail || JSON.stringify(err);
      } catch {}
      throw new Error(detail);
    }
    const blob = await res.blob();
    const cd = res.headers.get('Content-Disposition') || '';
    const match = cd.match(/filename=([^;]+)/);
    const filename = match ? match[1] : `report_${scanId}.docx`;
    return { blob, filename };
  },
  refreshArtifacts: (scanId) => _request('POST', `/reports/${scanId}/refresh-artifacts`),
};

export default api;
