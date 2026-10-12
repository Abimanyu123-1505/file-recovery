/**
 * Main App – 6-step workbench layout with sidebar stepper.
 */
import { useState } from 'react';
import { WorkbenchProvider, useWorkbench, canGoToStep } from './context/WorkbenchContext';
import CaseDetails from './pages/CaseDetails';
import SelectEvidence from './pages/SelectEvidence';
import Analysis from './pages/Analysis';
import ReviewFiles from './pages/ReviewFiles';
import Recover from './pages/Recover';
import Report from './pages/Report';
import HelpDrawer from './components/HelpDrawer';
import './index.css';

const STEPS = [
  { num: 1, label: 'Case details',          desc: 'Case number and examiner information' },
  { num: 2, label: 'Select evidence',        desc: 'Choose the evidence image file' },
  { num: 3, label: 'Analysis',               desc: 'Scan for deleted files' },
  { num: 4, label: 'Review deleted files',   desc: 'Select files to recover' },
  { num: 5, label: 'Recover',               desc: 'Save copies of selected files' },
  { num: 6, label: 'Report',                desc: 'Generate and download the report' },
];

function Sidebar({ onHelpOpen }) {
  const { state, dispatch } = useWorkbench();

  function handleStepClick(step) {
    if (canGoToStep(state, step)) {
      dispatch({ type: 'SET_STEP', payload: step });
    }
  }

  return (
    <nav className="sidebar" aria-label="Workflow steps">
      <div className="sidebar-brand">
        <div className="sidebar-brand-title">
          EXT4 Recovery<br />Workbench
        </div>
        {state.caseData?.case_number && (
          <div className="sidebar-case-info">
            <div>Case</div>
            <div className="sidebar-case-number">{state.caseData.case_number}</div>
            {state.caseData.examiner_name && (
              <div style={{ marginTop: '4px' }}>{state.caseData.examiner_name}</div>
            )}
          </div>
        )}
      </div>

      <div className="sidebar-nav">
        <div className="sidebar-nav-label">Workflow</div>
        {STEPS.map(step => {
          const isActive = state.currentStep === step.num;
          const isDone = state.completedSteps.includes(step.num);
          const canGo = canGoToStep(state, step.num);

          return (
            <button
              key={step.num}
              type="button"
              className={`step-item ${isActive ? 'active' : ''}`}
              onClick={() => handleStepClick(step.num)}
              disabled={!canGo}
              aria-current={isActive ? 'step' : undefined}
              aria-disabled={!canGo}
              title={!canGo ? 'Complete previous steps first' : step.desc}
              id={`step-nav-${step.num}`}
            >
              <span className={`step-badge ${isDone ? 'completed' : isActive ? 'current' : ''}`}>
                {isDone ? '✓' : step.num}
              </span>
              <span className="step-label">{step.label}</span>
            </button>
          );
        })}
      </div>

      <div className="sidebar-footer">
        <div>EXT4 Recovery Workbench v0.1.0</div>
        <div style={{ marginTop: '4px' }}>
          <button
            type="button"
            onClick={onHelpOpen}
            style={{ background: 'none', border: 'none', color: 'rgba(200,214,232,0.7)', fontSize: '12px', cursor: 'pointer', padding: 0, textDecoration: 'underline' }}
          >
            Help &amp; glossary
          </button>
        </div>
      </div>
    </nav>
  );
}

function StepContent() {
  const { state } = useWorkbench();
  switch (state.currentStep) {
    case 1: return <CaseDetails />;
    case 2: return <SelectEvidence />;
    case 3: return <Analysis />;
    case 4: return <ReviewFiles />;
    case 5: return <Recover />;
    case 6: return <Report />;
    default: return <CaseDetails />;
  }
}

function WorkbenchApp() {
  const [helpOpen, setHelpOpen] = useState(false);

  return (
    <div className="app-layout">
      <Sidebar onHelpOpen={() => setHelpOpen(true)} />

      <div className="main-content">
        <div
          className="readonly-banner"
          role="banner"
          aria-label="Read-only notice"
        >
          <span className="readonly-banner-icon" aria-hidden="true">🔒</span>
          Original evidence is opened read-only and is never changed.
        </div>

        <main className="content-container" id="main-content">
          <StepContent />
        </main>
      </div>

      {helpOpen && <HelpDrawer onClose={() => setHelpOpen(false)} />}

      <button
        type="button"
        className="help-btn"
        onClick={() => setHelpOpen(true)}
        aria-label="Open help and glossary"
        title="Help"
      >
        ?
      </button>
    </div>
  );
}

export default function App() {
  return (
    <WorkbenchProvider>
      <WorkbenchApp />
    </WorkbenchProvider>
  );
}
