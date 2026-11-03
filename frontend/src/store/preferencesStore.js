import { useEffect, useSyncExternalStore } from 'react';
import { api } from '../api/client';
import { DEFAULT_BOARD_PREFS } from '../lib/boardThemes';

// The signed-in user's board preferences, loaded once from
// /account/settings and shared by every board on the page.
let state = { prefs: DEFAULT_BOARD_PREFS, status: 'idle' };
const listeners = new Set();

function emit(next) {
  state = next;
  listeners.forEach((listener) => listener());
}

function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function load() {
  if (state.status !== 'idle') return;
  state = { ...state, status: 'loading' };
  api('/account/settings')
    .then((settings) =>
      emit({ prefs: { ...DEFAULT_BOARD_PREFS, ...settings.board }, status: 'ready' }),
    )
    .catch(() => emit({ ...state, status: 'ready' }));
}

export function useBoardPrefs() {
  const snapshot = useSyncExternalStore(subscribe, () => state);
  useEffect(load, []);
  return snapshot.prefs;
}

/** Called after settings are saved, so open boards update at once. */
export function setBoardPrefs(prefs) {
  emit({ prefs: { ...DEFAULT_BOARD_PREFS, ...prefs }, status: 'ready' });
}

/** Forget cached preferences (on sign-out). */
export function resetBoardPrefs() {
  emit({ prefs: DEFAULT_BOARD_PREFS, status: 'idle' });
}
