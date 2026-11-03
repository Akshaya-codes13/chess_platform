import { useEffect, useSyncExternalStore } from 'react';
import { api } from '../api/client';

// Unread notification count for the sidebar bell, refreshed every minute
// while a portal page is open and right after the user reads notifications.
const POLL_MS = 60_000;
let unread = 0;
const listeners = new Set();

function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function refreshUnreadCount() {
  return api('/notifications/unread-count')
    .then((data) => {
      if (data.unread !== unread) {
        unread = data.unread;
        listeners.forEach((listener) => listener());
      }
    })
    .catch(() => {});
}

// One poller however many bells are mounted (sidebar and mobile bar).
let pollers = 0;
let timer = null;

export function useUnreadCount() {
  const count = useSyncExternalStore(subscribe, () => unread);
  useEffect(() => {
    pollers += 1;
    if (pollers === 1) {
      refreshUnreadCount();
      timer = setInterval(refreshUnreadCount, POLL_MS);
    }
    return () => {
      pollers -= 1;
      if (pollers === 0) clearInterval(timer);
    };
  }, []);
  return count;
}
