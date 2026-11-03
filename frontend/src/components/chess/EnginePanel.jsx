import { Chess } from 'chess.js';
import { useEffect, useState } from 'react';
import { formatScore, whitePercent } from '../../lib/uci';
import { useStockfish } from '../../lib/useStockfish';

function pvToSan(fen, pv, limit = 8) {
  const game = new Chess(fen);
  const sans = [];
  for (const uci of pv.slice(0, limit)) {
    try {
      sans.push(game.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] }).san);
    } catch {
      break;
    }
  }
  return sans;
}

/**
 * Browser Stockfish analysis for one position: evaluation bar, depth and
 * the best lines in SAN. `onBestMove` receives the top line's first move
 * (UCI) so the board can draw an arrow.
 */
export default function EnginePanel({ fen, onBestMove }) {
  const [enabled, setEnabled] = useState(false);
  const { status, error, lines, depth } = useStockfish(fen, { enabled });
  const best = lines[0];
  const gameOver = (() => {
    try {
      return new Chess(fen).isGameOver();
    } catch {
      return true;
    }
  })();

  const bestMove = enabled ? (best?.pv[0] ?? null) : null;
  useEffect(() => {
    onBestMove?.(bestMove);
  }, [bestMove, onBestMove]);

  return (
    <section className="engine-panel" aria-label="Engine analysis">
      <div className="engine-header">
        <h2 className="panel-heading">Stockfish</h2>
        <label className="switch">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(event) => setEnabled(event.target.checked)}
          />
          <span>{enabled ? 'On' : 'Off'}</span>
        </label>
      </div>

      {!enabled && <p className="row-meta">Turn the engine on to analyse this position.</p>}
      {enabled && status === 'loading' && <p className="row-meta">Loading the engine…</p>}
      {enabled && error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {enabled && gameOver && <p className="row-meta">The game is over in this position.</p>}

      {enabled && !gameOver && best && (
        <>
          <div className="eval-row">
            <div
              className="eval-bar"
              role="meter"
              aria-label="Evaluation for White"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={whitePercent(best.score)}
            >
              <span style={{ width: `${whitePercent(best.score)}%` }} />
            </div>
            <strong className="eval-score">{formatScore(best.score)}</strong>
            <span className="row-meta">
              depth {depth}
              {status === 'searching' ? '…' : ''}
            </span>
          </div>
          <ol className="engine-lines">
            {lines.map((line) => (
              <li key={line.multipv}>
                <span className="eval-score">{formatScore(line.score)}</span>{' '}
                <span className="engine-pv">{pvToSan(fen, line.pv).join(' ')}</span>
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}
