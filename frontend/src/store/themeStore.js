import { useSyncExternalStore } from 'react';

const STORAGE_KEY = 'theme';
const listeners = new Set();

// index.html sets data-theme before first paint (saved choice, else the OS preference).
function readTheme() {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Storage blocked: the choice still applies for this page load.
  }
  listeners.forEach((listener) => listener());
}

function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useTheme() {
  const theme = useSyncExternalStore(subscribe, readTheme);
  return { theme, setTheme };
}
