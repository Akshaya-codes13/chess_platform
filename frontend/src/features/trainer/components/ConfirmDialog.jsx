import { useEffect, useRef } from 'react';

/**
 * Modal confirmation built on <dialog>, which provides focus trapping,
 * Escape-to-close and an inert background natively.
 */
export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  tone = 'primary',
  busy = false,
  onConfirm,
  onCancel,
}) {
  const ref = useRef(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className="tr-dialog"
      aria-labelledby="tr-dialog-title"
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onCancel();
      }}
    >
      <h2 id="tr-dialog-title" className="tr-dialog__title">
        {title}
      </h2>
      <div className="tr-dialog__body">{message}</div>
      <div className="tr-dialog__actions">
        <button type="button" className="tr-btn tr-btn--ghost" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
        <button
          type="button"
          className={`tr-btn tr-btn--${tone}`}
          onClick={onConfirm}
          disabled={busy}
          autoFocus
        >
          {busy ? 'Working…' : confirmLabel}
        </button>
      </div>
    </dialog>
  );
}
