/**
 * Stepper tests: step blocking, step advancement, complete flow.
 */
import { describe, it, expect } from 'vitest';
import { canGoToStep } from '../context/WorkbenchContext';

describe('canGoToStep – stepper blocking', () => {
  const baseState = { currentStep: 1, completedSteps: [] };

  it('always allows going to step 1', () => {
    expect(canGoToStep(baseState, 1)).toBe(true);
  });

  it('blocks step 2 if step 1 not complete', () => {
    expect(canGoToStep(baseState, 2)).toBe(false);
  });

  it('allows step 2 when step 1 is complete', () => {
    const state = { ...baseState, completedSteps: [1] };
    expect(canGoToStep(state, 2)).toBe(true);
  });

  it('blocks step 4 if steps 1-3 not all complete', () => {
    const state = { ...baseState, completedSteps: [1, 2] };
    expect(canGoToStep(state, 4)).toBe(false);
  });

  it('allows step 4 when steps 1-3 all complete', () => {
    const state = { ...baseState, completedSteps: [1, 2, 3] };
    expect(canGoToStep(state, 4)).toBe(true);
  });

  it('allows going back to any already-seen step', () => {
    const state = { currentStep: 4, completedSteps: [1, 2, 3] };
    expect(canGoToStep(state, 2)).toBe(true);
    expect(canGoToStep(state, 1)).toBe(true);
  });

  it('blocks skipping from step 1 to step 6', () => {
    const state = { currentStep: 1, completedSteps: [1] };
    expect(canGoToStep(state, 6)).toBe(false);
  });

  it('allows step 6 when all previous steps complete', () => {
    const state = { currentStep: 6, completedSteps: [1, 2, 3, 4, 5] };
    expect(canGoToStep(state, 6)).toBe(true);
  });
});
