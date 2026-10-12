/**
 * Tooltip – wraps a label with a (?) button and popover explanation.
 */
import { useState } from 'react';

export default function Tooltip({ label, text, children }) {
  const [show, setShow] = useState(false);

  return (
    <span className="tooltip-wrapper">
      {children || label}
      <button
        type="button"
        className="tooltip-trigger"
        aria-label={`What does "${label}" mean?`}
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        onFocus={() => setShow(true)}
        onBlur={() => setShow(false)}
      >
        ?
      </button>
      {show && (
        <span className="tooltip-bubble" role="tooltip">
          {text}
        </span>
      )}
    </span>
  );
}
