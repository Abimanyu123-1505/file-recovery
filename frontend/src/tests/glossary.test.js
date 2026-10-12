/**
 * Frontend tests: stepper blocking, glossary, error mapping, report checklist, integrity warning.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { plain, tooltip, friendlyError, formatSize, formatDate, NAME_CONFIDENCE } from '../lib/glossary';

// ── Glossary tests ─────────────────────────────────────────────────────────

describe('glossary – term substitution', () => {
  it('maps inode to "file record"', () => {
    expect(plain('inode')).toBe('file record');
  });

  it('maps sha256 to "digital fingerprint"', () => {
    expect(plain('sha256')).toBe('digital fingerprint');
  });

  it('maps hash to "digital fingerprint"', () => {
    expect(plain('hash')).toBe('digital fingerprint');
  });

  it('maps FULL status', () => {
    expect(plain('FULL')).toBe('Fully recovered');
  });

  it('maps PARTIAL status', () => {
    expect(plain('PARTIAL')).toBe('Partly recovered – some data is missing');
  });

  it('maps FAILED status', () => {
    expect(plain('FAILED')).toBe('Could not be recovered');
  });

  it('returns key for unknown terms', () => {
    expect(plain('unknown_term_xyz')).toBe('unknown_term_xyz');
  });

  it('provides tooltip for inode', () => {
    const t = tooltip('inode');
    expect(t.length).toBeGreaterThan(0);
  });

  it('formats bytes correctly', () => {
    expect(formatSize(0)).toBe('0 bytes');
    expect(formatSize(500)).toBe('500 bytes');
    expect(formatSize(1024)).toBe('1.0 KB');
    expect(formatSize(1024 * 1024)).toBe('1.00 MB');
  });

  it('formatDate returns "Not recorded" for null/empty', () => {
    expect(formatDate(null)).toBe('Not recorded');
    expect(formatDate('')).toBe('Not recorded');
  });

  it('formatDate formats ISO string with UTC label', () => {
    const result = formatDate('2026-06-18T09:06:00Z');
    expect(result).toContain('2026');
    expect(result).toContain('UTC');
  });
});

// ── Name confidence ────────────────────────────────────────────────────────

describe('name confidence labels', () => {
  it('confirmed has success badge', () => {
    expect(NAME_CONFIDENCE.confirmed.badge).toBe('success');
    expect(NAME_CONFIDENCE.confirmed.label).toBe('Name confirmed');
  });

  it('uncertain has caution badge', () => {
    expect(NAME_CONFIDENCE.uncertain.badge).toBe('caution');
  });

  it('none has neutral badge', () => {
    expect(NAME_CONFIDENCE.none.badge).toBe('neutral');
  });
});

// ── Friendly error mapping ─────────────────────────────────────────────────

describe('friendlyError', () => {
  it('maps "evidence file not found" to friendly message', () => {
    const { friendly } = friendlyError('Evidence file not found');
    expect(friendly).toMatch(/couldn't find/i);
  });

  it('maps "permission denied" to friendly message', () => {
    const { friendly } = friendlyError('Permission denied to read the file');
    expect(friendly).toMatch(/access was denied/i);
  });

  it('maps "integrity.*failed" to critical message', () => {
    const { friendly, action } = friendlyError('integrity check failed');
    expect(friendly).toMatch(/changed during analysis/i);
    expect(action).toMatch(/supervisor/i);
  });

  it('returns generic message for unknown errors', () => {
    const { friendly } = friendlyError('some completely unknown error xyz123');
    expect(friendly.length).toBeGreaterThan(0);
  });

  it('accepts an Error object', () => {
    const { friendly } = friendlyError(new Error('Evidence file not found'));
    expect(friendly).toMatch(/couldn't find/i);
  });

  it('accepts an object with detail property', () => {
    const { friendly } = friendlyError({ detail: 'Permission denied' });
    expect(friendly).toMatch(/access was denied/i);
  });
});
