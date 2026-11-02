import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';

/** Fetch `path` (with optional `query`) and track loading/error state. */
export function useApi(path, { query, skip = false } = {}) {
  const queryKey = JSON.stringify(query ?? {});
  const [version, setVersion] = useState(0);
  const requestKey = `${path}|${queryKey}|${version}`;
  // `key` records which request the stored result belongs to, so loading is
  // derived instead of being set synchronously inside the effect.
  const [state, setState] = useState({ key: null, data: null, error: null });

  useEffect(() => {
    if (skip || !path) return undefined;
    const controller = new AbortController();

    api(path, { query: JSON.parse(queryKey), signal: controller.signal })
      .then((data) => setState({ key: requestKey, data, error: null }))
      .catch((error) => {
        if (error.name !== 'AbortError') setState({ key: requestKey, data: null, error });
      });

    return () => controller.abort();
  }, [path, queryKey, skip, requestKey]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  const setData = useCallback((data) => setState((s) => ({ ...s, data })), []);
  const loading = !skip && state.key !== requestKey;

  return {
    data: loading ? null : state.data,
    error: loading ? null : state.error,
    loading,
    reload,
    setData,
  };
}
