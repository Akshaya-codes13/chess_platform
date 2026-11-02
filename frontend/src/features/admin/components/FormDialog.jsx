import { useEffect, useId, useRef } from 'react';

/**
 * Modal form on <dialog> (native focus trap, Escape and inert background).
 * The submit button belongs to the form, so Enter submits it.
 */
export default function FormDialog({
  open,
  title,
  submitLabel = 'Save',
  busy = false,
  error,
  onSubmit,
  onClose,
  children,
}) {
  const ref = useRef(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className="tr-dialog ad-dialog"
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
    >
      {open && (
        <form
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit();
          }}
        >
          <h2 id={titleId} className="tr-dialog__title">
            {title}
          </h2>
          {error && (
            <p className="tr-callout tr-callout--error" role="alert">
              {error}
            </p>
          )}
          {children}
          <div className="tr-dialog__actions">
            <button
              type="button"
              className="tr-btn tr-btn--ghost"
              onClick={onClose}
              disabled={busy}
            >
              Cancel
            </button>
            <button type="submit" className="tr-btn tr-btn--primary" disabled={busy}>
              {busy ? 'Saving…' : submitLabel}
            </button>
          </div>
        </form>
      )}
    </dialog>
  );
}
