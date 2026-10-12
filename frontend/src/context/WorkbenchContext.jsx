/**
 * WorkbenchContext – persisted session state across all 6 workflow steps.
 * State is written to sessionStorage so a page refresh resumes at the correct step.
 */
import { createContext, useContext, useEffect, useReducer } from 'react';

const STORAGE_KEY = 'workbench_session';

const initialState = {
  currentStep: 1,   // 1-6
  completedSteps: [], // array of completed step numbers

  // Step 1
  caseId: null,
  caseData: null,

  // Step 2
  evidencePath: '',
  evidenceCheck: null,
  recentPaths: [],

  // Step 3
  scanId: null,
  scanStatus: null,
  scanResult: null,

  // Step 4
  candidates: [],
  selectedInodes: [],

  // Step 5
  recoveries: [],

  // Step 6
  reportProfile: 'general',
  reportType: 'investigator',
  declaration: null,
};

function reducer(state, action) {
  switch (action.type) {
    case 'SET_STEP':
      return { ...state, currentStep: action.payload };
    case 'COMPLETE_STEP': {
      const steps = Array.from(new Set([...state.completedSteps, action.payload]));
      return { ...state, completedSteps: steps };
    }
    case 'SET_CASE':
      return { ...state, caseId: action.payload.id, caseData: action.payload };
    case 'SET_EVIDENCE_PATH':
      return { ...state, evidencePath: action.payload };
    case 'SET_EVIDENCE_CHECK':
      return { ...state, evidenceCheck: action.payload };
    case 'ADD_RECENT_PATH': {
      const recent = [action.payload, ...state.recentPaths.filter(p => p !== action.payload)].slice(0, 5);
      return { ...state, recentPaths: recent };
    }
    case 'SET_SCAN':
      return { ...state, scanId: action.payload.id, scanStatus: action.payload.status };
    case 'SET_SCAN_STATUS':
      return { ...state, scanStatus: action.payload };
    case 'SET_SCAN_RESULT':
      return { ...state, scanResult: action.payload };
    case 'SET_CANDIDATES':
      return { ...state, candidates: action.payload };
    case 'SET_SELECTED_INODES':
      return { ...state, selectedInodes: action.payload };
    case 'SET_RECOVERIES':
      return { ...state, recoveries: action.payload };
    case 'SET_REPORT_OPTIONS':
      return { ...state, ...action.payload };
    case 'SET_DECLARATION':
      return { ...state, declaration: action.payload };
    case 'RESET':
      return { ...initialState };
    case 'HYDRATE':
      return { ...state, ...action.payload };
    default:
      return state;
  }
}

const WorkbenchContext = createContext(null);

export function WorkbenchProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState, (init) => {
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY);
      if (saved) return { ...init, ...JSON.parse(saved) };
    } catch {}
    return init;
  });

  // Persist to sessionStorage on every state change
  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {}
  }, [state]);

  return (
    <WorkbenchContext.Provider value={{ state, dispatch }}>
      {children}
    </WorkbenchContext.Provider>
  );
}

export function useWorkbench() {
  const ctx = useContext(WorkbenchContext);
  if (!ctx) throw new Error('useWorkbench must be used inside WorkbenchProvider');
  return ctx;
}

/**
 * Navigate to a step, enforcing forward-only skipping prevention.
 * A step can only be entered if the previous step is complete (or going back).
 */
export function canGoToStep(state, step) {
  if (step <= state.currentStep) return true; // always allow going back
  // To jump to step N, steps 1..N-1 must all be complete
  for (let s = 1; s < step; s++) {
    if (!state.completedSteps.includes(s)) return false;
  }
  return true;
}
