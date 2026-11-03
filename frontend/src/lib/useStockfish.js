import { useEffect, useRef, useState } from 'react';
import { parseInfo } from './uci';

const ENGINE_URL = `${import.meta.env.BASE_URL}stockfish/stockfish-19-lite-single.js`;

/**
 * Analyse `fen` with Stockfish (lite, single-threaded WASM) in a Web Worker.
 *
 * Returns { status, lines, depth, error }. `lines` holds the best `multipv`
 * variations as { multipv, depth, score, pv } with UCI moves and scores
 * from White's point of view. A new position stops the running search
 * first, so lines from different positions never mix.
 */
export function useStockfish(fen, { enabled = true, depth = 18, multipv = 3 } = {}) {
  const workerRef = useRef(null);
  const searchRef = useRef({ fen: null, searching: false, pending: null });
  const [result, setResult] = useState({ fen: null, lines: [], depth: 0, done: false });
  const [error, setError] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!enabled) return undefined;
    let worker;
    try {
      worker = new Worker(ENGINE_URL);
    } catch {
      // The failure is reported through state on the next render.
      queueMicrotask(() => setError('The analysis engine could not be started in this browser.'));
      return undefined;
    }
    workerRef.current = worker;

    const start = (target) => {
      searchRef.current = { fen: target, searching: true, pending: null };
      setResult({ fen: target, lines: [], depth: 0, done: false });
      worker.postMessage(`position fen ${target}`);
      worker.postMessage(`go depth ${depth}`);
    };

    worker.onmessage = ({ data }) => {
      const line = String(data);
      const search = searchRef.current;

      if (line === 'uciok') {
        worker.postMessage(`setoption name MultiPV value ${multipv}`);
        worker.postMessage('isready');
      } else if (line === 'readyok') {
        setReady(true);
        if (search.pending) start(search.pending);
      } else if (line.startsWith('bestmove')) {
        if (search.pending) start(search.pending);
        else {
          searchRef.current = { ...search, searching: false };
          setResult((r) => (r.fen === search.fen ? { ...r, done: true } : r));
        }
      } else if (search.searching && !search.pending) {
        const info = parseInfo(line, search.fen?.split(' ')[1]);
        if (!info) return;
        setResult((r) => {
          if (r.fen !== search.fen) return r;
          const lines = r.lines.filter((l) => l.multipv !== info.multipv);
          lines.push(info);
          lines.sort((a, b) => a.multipv - b.multipv);
          return { ...r, lines, depth: Math.max(r.depth, info.depth) };
        });
      }
    };
    worker.onerror = () => setError('The analysis engine failed to load.');
    worker.postMessage('uci');

    // Exposed to the position effect below.
    worker.startSearch = (target) => {
      if (searchRef.current.searching) {
        searchRef.current = { ...searchRef.current, pending: target };
        worker.postMessage('stop');
      } else {
        start(target);
      }
    };

    return () => {
      worker.postMessage('quit');
      worker.terminate();
      workerRef.current = null;
      searchRef.current = { fen: null, searching: false, pending: null };
      setReady(false);
    };
  }, [enabled, depth, multipv]);

  useEffect(() => {
    const worker = workerRef.current;
    if (!enabled || !worker || !fen) return;
    if (!ready) {
      searchRef.current = { ...searchRef.current, pending: fen };
      return;
    }
    worker.startSearch(fen);
  }, [fen, enabled, ready]);

  const current = result.fen === fen ? result : { lines: [], depth: 0, done: false };
  let status = 'idle';
  if (error) status = 'error';
  else if (enabled && !ready) status = 'loading';
  else if (enabled) status = current.done ? 'done' : 'searching';

  return { status, error, lines: current.lines, depth: current.depth };
}
