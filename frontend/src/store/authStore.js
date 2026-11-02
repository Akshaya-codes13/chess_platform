import { useSyncExternalStore } from 'react';
import {
  api,
  getRefreshToken,
  hasRefreshToken,
  refreshSession,
  setSessionExpiredHandler,
  setTokens,
} from '../api/client';
import { navigate } from '../routes/router';

// status: 'loading' | 'authenticated' | 'anonymous'
let state = { user: null, status: hasRefreshToken() ? 'loading' : 'anonymous' };
const listeners = new Set();

function setState(next) {
  state = { ...state, ...next };
  listeners.forEach((listener) => listener());
}

function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

async function loadUser() {
  try {
    setState({ user: await api('/auth/me'), status: 'authenticated' });
  } catch {
    setTokens(null);
    setState({ user: null, status: 'anonymous' });
  }
}

async function login(email, password) {
  const tokens = await api('/auth/login', { method: 'POST', body: { email, password } });
  setTokens(tokens);
  await loadUser();
}

async function demoLogin(role) {
  const tokens = await api('/auth/demo-login', { method: 'POST', body: { role } });
  setTokens(tokens);
  await loadUser();
}

/** Create a student account, then sign straight in with it. */
async function register({ fullName, email, password }) {
  await api('/auth/register', {
    method: 'POST',
    body: { full_name: fullName, email, password },
  });
  await login(email, password);
}

async function logout() {
  const refreshToken = getRefreshToken();
  try {
    if (refreshToken)
      await api('/auth/logout', { method: 'POST', body: { refresh_token: refreshToken } });
  } catch {
    // The local session is cleared either way.
  } finally {
    setTokens(null);
    setState({ user: null, status: 'anonymous' });
    // The next account may have a different role, so do not keep this portal's page.
    navigate('/login', { replace: true });
  }
}

async function refreshUser() {
  if (state.status === 'authenticated') await loadUser();
}

setSessionExpiredHandler(() => {
  setTokens(null);
  setState({ user: null, status: 'anonymous' });
});

// Restore a session from the stored refresh token on startup.
if (state.status === 'loading') {
  refreshSession().then((ok) => (ok ? loadUser() : setState({ status: 'anonymous' })));
}

const actions = { login, demoLogin, register, logout, refreshUser };

export function useAuth() {
  const snapshot = useSyncExternalStore(subscribe, () => state);
  return { ...snapshot, ...actions };
}
