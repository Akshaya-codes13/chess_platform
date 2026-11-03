import { useCallback, useEffect, useState } from 'react';
import ChessBoard from '../../components/chess/ChessBoard';
import EnginePanel from '../../components/chess/EnginePanel';
import TrainerPage from '../../features/trainer/components/TrainerPage';
import { toast } from '../../features/trainer/components/toastStore';
import { Button, Loaded, PageHeader, Section } from '../../features/trainer/components/ui';
import { useLoader } from '../../features/trainer/hooks';
import { sharedApi } from '../../features/shared/api';
import { Link, useRoute } from '../../routes/router';
import { usePortalBase } from './base';

export default function GameViewerPage() {
  const { params } = useRoute();
  const result = useLoader(() => sharedApi.game(params.gameId), [params.gameId]);
  return (
    <TrainerPage>
      <Loaded result={result}>{(game) => <GameViewer game={game} />}</Loaded>
    </TrainerPage>
  );
}

function GameViewer({ game }) {
  const base = usePortalBase();
  const last = game.positions.length - 1;
  const [ply, setPly] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [bestMove, setBestMove] = useState(null);
  const position = game.positions[ply];
  const startsWithBlack = game.positions[0].fen.split(' ')[1] === 'b';
  const firstMoveNumber = Number(game.positions[0].fen.split(' ')[5]) || 1;

  const go = useCallback((target) => setPly(Math.max(0, Math.min(last, target))), [last]);

  useEffect(() => {
    function onKey(event) {
      if (event.target.closest('input, textarea, select')) return;
      const step = { ArrowLeft: -1, ArrowRight: 1 }[event.key];
      if (step) {
        event.preventDefault();
        setPly((current) => Math.max(0, Math.min(last, current + step)));
      } else if (event.key === 'Home') go(0);
      else if (event.key === 'End') go(last);
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [go, last]);

  const databaseCrumb = game.breadcrumbs.at(-1);
  const folderQuery = databaseCrumb?.id ? `?folder=${databaseCrumb.id}` : '';

  // Pair plies into numbered rows: [number, whitePly, blackPly].
  const rows = [];
  game.positions.slice(1).forEach((item) => {
    const index = item.ply - 1 + (startsWithBlack ? 1 : 0);
    const rowIndex = Math.floor(index / 2);
    rows[rowIndex] ??= { number: firstMoveNumber + rowIndex, white: null, black: null };
    rows[rowIndex][index % 2 === 0 ? 'white' : 'black'] = item;
  });

  const moveButton = (item) =>
    item ? (
      <button
        type="button"
        className={`move-chip ${item.ply === ply ? 'is-current' : ''}`}
        aria-current={item.ply === ply ? 'step' : undefined}
        onClick={() => go(item.ply)}
      >
        {item.san}
      </button>
    ) : (
      <span className="move-chip is-empty">…</span>
    );

  return (
    <>
      <PageHeader
        back={{
          to: `${base}/games/db/${game.database_id}${folderQuery}`,
          label: game.breadcrumbs.map((c) => c.name).join(' / '),
        }}
        title={`${game.white} – ${game.black}`}
        subtitle={[game.result, game.event, game.site, game.game_date, game.eco]
          .filter(Boolean)
          .join(' · ')}
      />

      <div className="viewer-layout">
        <div className="viewer-board">
          <ChessBoard
            fen={position.fen}
            orientation={flipped ? 'black' : 'white'}
            lastMove={
              position.uci ? { from: position.uci.slice(0, 2), to: position.uci.slice(2, 4) } : null
            }
            arrows={
              bestMove
                ? [
                    {
                      startSquare: bestMove.slice(0, 2),
                      endSquare: bestMove.slice(2, 4),
                      color: 'rgba(63, 122, 74, 0.8)',
                    },
                  ]
                : []
            }
            label="Game board"
          />
          <div className="board-controls" role="group" aria-label="Replay controls">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => go(0)}
              disabled={ply === 0}
              aria-label="Start"
            >
              ⏮
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => go(ply - 1)}
              disabled={ply === 0}
              aria-label="Previous move"
            >
              ◀
            </Button>
            <span className="tr-muted ply-counter">
              {ply}/{last}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => go(ply + 1)}
              disabled={ply === last}
              aria-label="Next move"
            >
              ▶
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => go(last)}
              disabled={ply === last}
              aria-label="End"
            >
              ⏭
            </Button>
            <Button variant="secondary" size="sm" onClick={() => setFlipped((value) => !value)}>
              Flip
            </Button>
          </div>
          <p className="tr-muted">Use ← and → to step through the game.</p>
        </div>

        <aside className="viewer-panel">
          <EnginePanel fen={position.fen} onBestMove={setBestMove} />

          <Section title="Moves">
            <ol className="move-table">
              {rows.map((row) => (
                <li key={row.number}>
                  <span className="move-number">{row.number}.</span>
                  {moveButton(row.white)}
                  {moveButton(row.black)}
                </li>
              ))}
            </ol>
            <p className="game-result">{game.result}</p>
          </Section>

          <Section title="Position">
            <code className="tr-code fen-line">{position.fen}</code>
            <div className="tr-page-actions">
              <Button
                variant="secondary"
                size="sm"
                onClick={() =>
                  navigator.clipboard
                    ?.writeText(position.fen)
                    .then(() => toast.success('FEN copied.'))
                    .catch(() => toast.error('Copy failed.'))
                }
              >
                Copy FEN
              </Button>
              <Link
                className="tr-btn tr-btn--ghost tr-btn--sm"
                to={`${base}/board-editor?fen=${encodeURIComponent(position.fen)}`}
              >
                Open in board editor
              </Link>
            </div>
          </Section>

          <details className="tr-card">
            <summary>PGN</summary>
            <pre className="pgn-text">{game.pgn}</pre>
          </details>
        </aside>
      </div>
    </>
  );
}
