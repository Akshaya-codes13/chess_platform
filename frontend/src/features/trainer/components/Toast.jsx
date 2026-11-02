import { useSyncExternalStore } from 'react';
import { dismissToast, getToasts, subscribeToasts } from './toastStore';

export function Toaster() {
  const items = useSyncExternalStore(subscribeToasts, getToasts);

  return (
    <div className="tr-toaster" aria-live="polite" aria-atomic="false">
      {items.map((item) => (
        <div
          key={item.id}
          className={`tr-toast tr-toast--${item.kind}`}
          role={item.kind === 'error' ? 'alert' : 'status'}
        >
          <span>{item.message}</span>
          <button
            type="button"
            className="tr-toast__close"
            onClick={() => dismissToast(item.id)}
            aria-label="Dismiss notification"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
