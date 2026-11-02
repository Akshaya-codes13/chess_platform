import { useMemo, useRef, useState } from 'react';
import {
  FILES,
  kingSquare,
  parseFen,
  pieceGlyph,
  pieceName,
  PROMOTION_PIECES,
} from '../../lib/fen';

/**
 * Interactive board driven entirely by server data: `fen` sets the position
 * and `legalMoves` (UCI strings computed by python-chess) decides which moves
 * may be played, so check, castling, en passant and promotion rules always
 * match the backend.
 */
export default function Board({
  fen,
  orientation = 'white',
  legalMoves = [],
  onMove,
  lastMove = null,
  interactive = true,
  inCheck = false,
}) {
  const { pieces, turn } = useMemo(() => parseFen(fen), [fen]);
  // Selection is tied to the position it was made in, so a new FEN clears it.
  const [selection, setSelection] = useState({ fen, square: null });
  const [promotion, setPromotion] = useState(null);
  const [focused, setFocused] = useState(null);
  const squareRefs = useRef({});

  const selected = selection.fen === fen ? selection.square : null;
  const pendingPromotion = promotion?.fen === fen ? promotion : null;

  const movesFrom = useMemo(() => {
    const map = {};
    legalMoves.forEach((uci) => {
      const from = uci.slice(0, 2);
      (map[from] ??= []).push(uci);
    });
    return map;
  }, [legalMoves]);

  const destinations = new Set((movesFrom[selected] ?? []).map((uci) => uci.slice(2, 4)));
  const checkSquare = inCheck ? kingSquare(pieces, turn) : null;

  const ranks = orientation === 'white' ? [8, 7, 6, 5, 4, 3, 2, 1] : [1, 2, 3, 4, 5, 6, 7, 8];
  const files = orientation === 'white' ? FILES.split('') : FILES.split('').reverse();
  const order = ranks.flatMap((rank) => files.map((file) => `${file}${rank}`));
  const focusSquare = focused && order.includes(focused) ? focused : (selected ?? order[0]);

  function select(square) {
    setSelection({ fen, square });
  }

  function handleSquare(square) {
    if (!interactive) return;

    if (selected && destinations.has(square)) {
      const candidates = movesFrom[selected].filter((uci) => uci.slice(2, 4) === square);
      if (candidates.some((uci) => uci.length === 5)) {
        setPromotion({ fen, from: selected, to: square });
        return;
      }
      select(null);
      onMove?.(candidates[0]);
      return;
    }

    if (square === selected) {
      select(null);
    } else if (movesFrom[square]) {
      select(square);
    } else {
      select(null);
    }
  }

  function choosePromotion(code) {
    const uci = `${pendingPromotion.from}${pendingPromotion.to}${code}`;
    setPromotion(null);
    select(null);
    onMove?.(uci);
  }

  function handleKeyDown(event, square) {
    const index = order.indexOf(square);
    const step = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: 8, ArrowUp: -8 }[event.key];
    if (step === undefined) {
      if (event.key === 'Escape') select(null);
      return;
    }
    event.preventDefault();
    const next = order[index + step];
    if (next) {
      setFocused(next);
      squareRefs.current[next]?.focus();
    }
  }

  return (
    <div className={`board-frame ${interactive ? '' : 'is-locked'}`}>
      <div className="board" role="grid" aria-label={`Chess board, ${turn} to move`}>
        {ranks.map((rank, rowIndex) => (
          <div className="board-row" role="row" key={rank}>
            {files.map((file, colIndex) => {
              const square = `${file}${rank}`;
              const piece = pieces[square];
              // a1 is dark: file index 0 + rank 1 is odd.
              const isDark = (FILES.indexOf(file) + rank) % 2 === 1;
              const classes = [
                'square',
                isDark ? 'is-dark' : 'is-light',
                square === selected && 'is-selected',
                destinations.has(square) && (piece ? 'is-capture' : 'is-target'),
                lastMove && (lastMove.from === square || lastMove.to === square) && 'is-last',
                square === checkSquare && 'is-check',
              ]
                .filter(Boolean)
                .join(' ');

              const label = [
                square,
                piece ? pieceName(piece) : 'empty',
                destinations.has(square) ? (piece ? 'capture available' : 'move available') : '',
                square === selected ? 'selected' : '',
              ]
                .filter(Boolean)
                .join(', ');

              return (
                <button
                  key={square}
                  ref={(node) => {
                    squareRefs.current[square] = node;
                  }}
                  type="button"
                  role="gridcell"
                  className={classes}
                  aria-label={label}
                  aria-pressed={square === selected}
                  tabIndex={square === focusSquare ? 0 : -1}
                  onFocus={() => setFocused(square)}
                  onClick={() => handleSquare(square)}
                  onKeyDown={(event) => handleKeyDown(event, square)}
                  disabled={!interactive && !piece}
                >
                  {piece && (
                    <span className={`piece piece-${piece.color}`} aria-hidden="true">
                      {pieceGlyph(piece)}
                    </span>
                  )}
                  {colIndex === 0 && (
                    <span className="coord coord-rank" aria-hidden="true">
                      {rank}
                    </span>
                  )}
                  {rowIndex === 7 && (
                    <span className="coord coord-file" aria-hidden="true">
                      {file}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </div>

      {pendingPromotion && (
        <div className="promotion" role="dialog" aria-label="Choose a promotion piece">
          <p>Promote to</p>
          <div className="promotion-choices">
            {PROMOTION_PIECES.map(({ code, label }) => (
              <button
                key={code}
                type="button"
                className="promotion-choice"
                onClick={() => choosePromotion(code)}
              >
                <span className={`piece piece-${turn}`} aria-hidden="true">
                  {pieceGlyph({ type: code })}
                </span>
                {label}
              </button>
            ))}
          </div>
          <button type="button" className="link-button" onClick={() => setPromotion(null)}>
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}
