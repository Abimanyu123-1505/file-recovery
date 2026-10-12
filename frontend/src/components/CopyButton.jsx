/**
 * CopyButton – copies text to clipboard with visual feedback.
 */
import { useState } from 'react';

export default function CopyButton({ text, label = 'Copy' }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback
    }
  }

  return (
    <button
      type="button"
      className="btn btn--secondary btn--sm"
      onClick={handleCopy}
      aria-label={`Copy ${label} to clipboard`}
    >
      {copied ? 'Copied' : label}
    </button>
  );
}
