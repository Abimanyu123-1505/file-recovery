/**
 * Glossary – plain-language term substitutions for the UI.
 * Import this and use glossary.term() or glossary.tooltip() everywhere.
 *
 * Rule: every technical term presented to the user must go through this
 * file, or be wrapped in a Tooltip component with an explanation from here.
 */

export const TERMS = {
  inode: {
    plain: 'file record',
    tooltip: 'An internal entry in the file system that stores information about a file, such as its size and storage location.',
  },
  sha256: {
    plain: 'digital fingerprint',
    tooltip: 'A unique mathematical code calculated from the file contents. Any change to the file produces a different code.',
  },
  hash: {
    plain: 'digital fingerprint',
    tooltip: 'A unique mathematical code calculated from the file contents. Any change to the file produces a different code.',
  },
  integrity_ok: {
    plain: 'Evidence unchanged during analysis',
    tooltip: 'The digital fingerprint before and after analysis was identical, confirming the original evidence was not altered.',
  },
  deletion_time: {
    plain: 'date deleted',
    tooltip: 'The recorded date and time when the file was removed, according to the file system.',
  },
  extent_recovery: {
    plain: 'recovered from stored data',
    tooltip: 'The file data was read directly from the areas of storage where it was originally written.',
  },
  slack: {
    plain: 'leftover data',
    tooltip: 'Small amounts of data that may remain in storage space that was previously used by a deleted file.',
  },
  journal: {
    plain: 'file system activity log',
    tooltip: 'An internal record kept by EXT4 that logs recent changes to the file system, used to verify consistency.',
  },
  pytsk3_crosscheck: {
    plain: 'independent verification',
    tooltip: 'The finding was confirmed using a separate forensic analysis tool (The Sleuth Kit), providing an additional layer of assurance.',
  },
  tsk: {
    plain: 'independent verification tool',
    tooltip: 'The Sleuth Kit – a widely-used, open-source forensic analysis library used to cross-check results.',
  },
  ext4: {
    plain: 'EXT4 file system',
    tooltip: 'A common type of file system used on Linux-based computers and devices. This tool analyses EXT4 images.',
  },
  alloc: {
    plain: 'in use',
    tooltip: 'Storage space currently assigned to an active file.',
  },
  unalloc: {
    plain: 'no longer in use',
    tooltip: 'Storage space that was previously used by a file but has since been marked as available for new data.',
  },
  FULL: {
    plain: 'Fully recovered',
    tooltip: 'The recovered copy is the same size as the original file record. It may still contain errors if blocks were reused.',
  },
  PARTIAL: {
    plain: 'Partly recovered – some data is missing',
    tooltip: 'Only part of the file could be recovered. The rest may have been overwritten by other data.',
  },
  FAILED: {
    plain: 'Could not be recovered',
    tooltip: 'No usable data could be read for this file record.',
  },
};

/**
 * Return the plain-language term for a technical key.
 * Falls back to the key itself if not found.
 */
export function plain(key) {
  return TERMS[key]?.plain ?? key;
}

/**
 * Return the tooltip text for a technical key.
 */
export function tooltip(key) {
  return TERMS[key]?.tooltip ?? '';
}

/**
 * Map backend error strings to friendly messages with suggested action.
 */
export const ERROR_MAP = [
  {
    pattern: /evidence file not found/i,
    friendly: "We couldn't find that file. Check the path and try again.",
    action: "Go back and re-enter the file path.",
  },
  {
    pattern: /permission denied/i,
    friendly: "Access was denied to that file.",
    action: "Try running the Workbench as an administrator.",
  },
  {
    pattern: /not an ext4/i,
    friendly: "That file doesn't appear to be an EXT4 evidence image.",
    action: "Check that you have selected the correct file.",
  },
  {
    pattern: /integrity.*failed/i,
    friendly: "The evidence file changed during analysis.",
    action: "Do not rely on these results. Contact your supervisor immediately.",
  },
  {
    pattern: /analysis must be complete/i,
    friendly: "The analysis has not finished yet.",
    action: "Wait for the analysis to complete before recovering files.",
  },
  {
    pattern: /integrity check failed/i,
    friendly: "Recovery is disabled because the evidence file changed during analysis.",
    action: "Contact your supervisor before proceeding.",
  },
  {
    pattern: /pytsk3.*required/i,
    friendly: "A required forensic library is not installed.",
    action: "Contact your system administrator to install the required software.",
  },
  {
    pattern: /network|timeout|fetch/i,
    friendly: "Could not connect to the analysis service.",
    action: "Check that the Workbench service is running and try again.",
  },
];

/**
 * Map a raw error string/object to a friendly message.
 * Returns { friendly, action } or falls back to a generic message.
 */
export function friendlyError(err) {
  const message = typeof err === 'string' ? err : (err?.detail || err?.message || String(err));
  for (const entry of ERROR_MAP) {
    if (entry.pattern.test(message)) {
      return { friendly: entry.friendly, action: entry.action };
    }
  }
  return {
    friendly: "Something went wrong. Please try again.",
    action: "If the problem continues, contact your supervisor or IT support.",
  };
}

/**
 * Format a date (ISO string or Date) in a clear, readable format with timezone.
 * Example: "18 Jun 2026, 09:06 UTC"
 */
export function formatDate(isoString, options = {}) {
  if (!isoString) return 'Not recorded';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    const dateStr = d.toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      timeZone: 'UTC',
    });
    if (options.dateOnly) return dateStr;
    const timeStr = d.toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'UTC',
    });
    return `${dateStr}, ${timeStr} UTC`;
  } catch {
    return isoString;
  }
}

/**
 * Format bytes as a human-readable string.
 */
export function formatSize(bytes) {
  if (bytes == null) return 'Unknown';
  if (bytes < 1024) return `${bytes} bytes`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

/**
 * Name confidence labels and notes.
 */
export const NAME_CONFIDENCE = {
  confirmed: {
    label: 'Name confirmed',
    note: 'The file name was found in a surviving directory record – the most reliable source.',
    badge: 'success',
  },
  uncertain: {
    label: 'Name uncertain – found in leftover data',
    note: 'The file name was found in unallocated storage remnants. It may not be the original name.',
    badge: 'caution',
  },
  none: {
    label: 'Original name not available',
    note: 'No surviving record of the original file name was found.',
    badge: 'neutral',
  },
};
