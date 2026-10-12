/**
 * ConfirmDialog – modal requiring explicit confirmation before destructive actions.
 */
export default function ConfirmDialog({ title, message, confirmLabel = 'Confirm', cancelLabel = 'Cancel', onConfirm, onCancel, dangerous = false }) {
  return (
    <div className="dialog-overlay" role="dialog" aria-modal="true" aria-labelledby="dialog-title">
      <div className="dialog">
        <h2 className="dialog-title" id="dialog-title">{title}</h2>
        <p className="dialog-body">{message}</p>
        <div className="btn-row">
          <button
            type="button"
            className="btn btn--secondary"
            onClick={onCancel}
            autoFocus
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            className={`btn ${dangerous ? 'btn--danger' : 'btn--primary'}`}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
