// Toasts live in a module-level store so a toast raised just before
// navigating (e.g. "Puzzle created") survives the page change.
let toasts = [];
let nextId = 1;
const listeners = new Set();

function emit() {
  for (const listener of listeners) listener();
}

export function dismissToast(id) {
  toasts = toasts.filter((item) => item.id !== id);
  emit();
}

function push(kind, message) {
  const id = nextId++;
  toasts = [...toasts, { id, kind, message }];
  emit();
  setTimeout(() => dismissToast(id), kind === 'error' ? 7000 : 4000);
}

export const toast = {
  success: (message) => push('success', message),
  error: (message) => push('error', message),
  info: (message) => push('info', message),
};

export function subscribeToasts(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export const getToasts = () => toasts;
