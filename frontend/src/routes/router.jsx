/* eslint-disable react-refresh/only-export-components -- routing module: hooks and helpers live beside Link */
import { useSyncExternalStore } from 'react';

// Hash routing ("#/student/assignments") needs no server rewrites and no
// extra dependency.

function currentHash() {
  const raw = window.location.hash.replace(/^#/, '') || '/';
  const [path, search = ''] = raw.split('?');
  return { path: path || '/', search };
}

let snapshot = currentHash();

function subscribe(listener) {
  const handler = () => {
    snapshot = currentHash();
    listener();
  };
  window.addEventListener('hashchange', handler);
  return () => window.removeEventListener('hashchange', handler);
}

export function navigate(to, { replace = false } = {}) {
  const target = `#${to}`;
  if (replace) window.location.replace(target);
  else window.location.hash = to;
}

function compile(pattern) {
  const keys = [];
  const regex = pattern.replace(/\/:([A-Za-z]+)/g, (_, key) => {
    keys.push(key);
    return '/([^/]+)';
  });
  return { regex: new RegExp(`^${regex}/?$`), keys };
}

export function matchRoute(routes, path) {
  for (const route of routes) {
    const { regex, keys } = compile(route.path);
    const match = path.match(regex);
    if (match) {
      const params = Object.fromEntries(
        keys.map((key, i) => [key, decodeURIComponent(match[i + 1])]),
      );
      return { route, params };
    }
  }
  return null;
}

export function useLocation() {
  return useSyncExternalStore(subscribe, () => snapshot);
}

/** The current path, its matched params (set by AppRouter) and the query. */
export function useRoute(routes) {
  const { path, search } = useLocation();
  const query = Object.fromEntries(new URLSearchParams(search));
  const match = routes ? matchRoute(routes, path) : matchRoute(activeRoutes, path);
  return { path, params: match?.params ?? {}, query, route: match?.route ?? null };
}

let activeRoutes = [];

export function setActiveRoutes(routes) {
  activeRoutes = routes;
}

/** Whether nav item `to` should be highlighted for `path`. */
export function isActive(path, to) {
  return path === to || path.startsWith(`${to}/`);
}

export function Link({ to, children, className, ...rest }) {
  return (
    <a href={`#${to}`} className={className} {...rest}>
      {children}
    </a>
  );
}
