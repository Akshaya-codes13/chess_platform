import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Run an async loader and track { data, error, loading }. The loader re-runs
 * when any value in `deps` changes (or after `reload()`); responses from
 * superseded requests are ignored so fast filter changes cannot show stale
 * results. Previous data stays visible while the next request is in flight.
 */
export function useLoader(loader, deps) {
  const [nonce, setNonce] = useState(0);
  const key = JSON.stringify([...deps, nonce]);
  const [state, setState] = useState({ data: null, error: null, key: null });
  const loaderRef = useRef(loader);

  useEffect(() => {
    loaderRef.current = loader;
  });

  useEffect(() => {
    let cancelled = false;
    loaderRef.current().then(
      (data) => !cancelled && setState({ data, error: null, key }),
      (error) => !cancelled && setState((current) => ({ ...current, error, key })),
    );
    return () => {
      cancelled = true;
    };
  }, [key]);

  const reload = useCallback(() => setNonce((value) => value + 1), []);

  return { data: state.data, error: state.error, loading: state.key !== key, reload };
}

/** Delay a fast-changing value (e.g. a search box) before using it. */
export function useDebounced(value, delay = 300) {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}

/** List filters plus page number; changing a filter resets to page 1. */
export function useListState(initial) {
  const [filters, setFilters] = useState({ page: 1, page_size: 20, ...initial });

  const setFilter = useCallback((name, value) => {
    setFilters((current) => ({ ...current, [name]: value, page: name === 'page' ? value : 1 }));
  }, []);

  return [filters, setFilter];
}
