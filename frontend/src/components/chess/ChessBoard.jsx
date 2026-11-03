import { Chess } from 'chess.js';
import { useId, useMemo, useState } from 'react';
import { Chessboard, defaultPieces } from 'react-chessboard';
import { boardColors, glyphPieceList } from '../../lib/boardThemes';
import { PROMOTION_PIECES } from '../../lib/fen';
import { useBoardPrefs } from '../../store/preferencesStore';

const GLYPH_PIECES = Object.fromEntries(
  glyphPieceList().map(({ code, color, glyph }) => [
    code,
    (props) => (
      <svg viewBox="0 0 45 45" width="100%" height="100%" style={props?.svgStyle}>
        <text
          x="22.5"
          y="25"
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize="38"
          fill={color === 'w' ? '#fffaf3' : '#2e1b10'}
          stroke={color === 'w' ? '#2e1b10' : '#fffaf3'}
          strokeWidth="1"
        >
          {glyph}
        </text>
      </svg>
    ),
  ]),
);

function legalFrom(fen) {
  try {
    return new Chess(fen).moves({ verbose: true }).map((m) => m.lan);
  } catch {
    return [];
  }
}

/**
 * The academy's chess board (react-chessboard), styled with the signed-in
 * user's board theme and piece set.
 *
 * Moves are offered only from `legalMoves` (UCI strings). Puzzles pass the
 * list computed by the server; elsewhere it defaults to chess.js's legal
 * moves for `fen`. `onMove(uci)` makes the board interactive (drag or click),
 * and a "type a move" field keeps it usable from the keyboard.
 */
export default function ChessBoard({
  fen,
  orientation = 'white',
  onMove,
  legalMoves,
  interactive = Boolean(onMove),
  lastMove = null,
  highlights = {},
  arrows = [],
  inCheck = false,
  label = 'Chess board',
  // Overrides the saved preferences (used by the settings preview).
  prefs: prefsOverride,
}) {
  const savedPrefs = useBoardPrefs();
  const prefs = prefsOverride ?? savedPrefs;
  const id = useId();
  const colors = boardColors(prefs.theme);
  const [selection, setSelection] = useState({ fen, square: null });
  const [promotion, setPromotion] = useState(null);
  const [typed, setTyped] = useState('');
  const [typedError, setTypedError] = useState('');

  const moves = useMemo(
    () => (interactive ? (legalMoves ?? legalFrom(fen)) : []),
    [interactive, legalMoves, fen],
  );
  const selected = selection.fen === fen ? selection.square : null;
  const pending = promotion?.fen === fen ? promotion : null;

  const movesFrom = useMemo(() => {
    const map = {};
    moves.forEach((uci) => (map[uci.slice(0, 2)] ??= []).push(uci));
    return map;
  }, [moves]);

  function attempt(from, to) {
    const candidates = (movesFrom[from] ?? []).filter((uci) => uci.slice(2, 4) === to);
    if (!candidates.length) return false;
    setSelection({ fen, square: null });
    if (candidates.some((uci) => uci.length === 5)) {
      setPromotion({ fen, from, to });
      return true;
    }
    onMove?.(candidates[0]);
    return true;
  }

  function onSquareClick({ square }) {
    if (!interactive) return;
    if (selected && attempt(selected, square)) return;
    setSelection({ fen, square: movesFrom[square] && square !== selected ? square : null });
  }

  function onPieceDrop({ sourceSquare, targetSquare }) {
    if (!interactive || !targetSquare) return false;
    return attempt(sourceSquare, targetSquare);
  }

  function submitTyped(event) {
    event.preventDefault();
    const text = typed.trim();
    if (!text) return;
    let uci = text.toLowerCase();
    if (!moves.includes(uci)) {
      try {
        const move = new Chess(fen).move(text);
        uci = move.lan;
      } catch {
        uci = null;
      }
    }
    if (!uci || !moves.includes(uci)) {
      setTypedError(`${text} is not a legal move here.`);
      return;
    }
    setTyped('');
    setTypedError('');
    onMove?.(uci);
  }

  const squareStyles = { ...highlights };
  if (lastMove) {
    squareStyles[lastMove.from] = { background: 'var(--color-board-last)' };
    squareStyles[lastMove.to] = { background: 'var(--color-board-last)' };
  }
  if (selected) {
    squareStyles[selected] = { background: 'var(--color-board-select)' };
    (movesFrom[selected] ?? []).forEach((uci) => {
      squareStyles[uci.slice(2, 4)] = {
        ...squareStyles[uci.slice(2, 4)],
        backgroundImage: 'radial-gradient(circle, rgba(59, 36, 22, 0.35) 22%, transparent 24%)',
      };
    });
  }
  if (inCheck) {
    const king = new Chess(fen, { skipValidation: true })
      .board()
      .flat()
      .find((piece) => piece?.type === 'k' && piece.color === fen.split(' ')[1]);
    if (king) {
      squareStyles[king.square] = {
        background: 'radial-gradient(circle, var(--color-board-check) 0%, transparent 75%)',
      };
    }
  }

  const turn = fen.split(' ')[1] === 'b' ? 'b' : 'w';

  return (
    <div className="chess-board-wrap">
      <div className={`board-frame ${interactive ? '' : 'is-locked'}`}>
        <div
          className="chessboard"
          role="img"
          aria-label={`${label}, ${turn === 'w' ? 'white' : 'black'} to move`}
        >
          <Chessboard
            options={{
              id: `board-${id}`,
              position: fen,
              boardOrientation: orientation,
              allowDragging: interactive,
              canDragPiece: ({ square }) => Boolean(square && movesFrom[square]),
              onPieceDrop,
              onSquareClick,
              squareStyles,
              arrows,
              lightSquareStyle: { backgroundColor: colors.light },
              darkSquareStyle: { backgroundColor: colors.dark },
              pieces: prefs.pieces === 'glyph' ? GLYPH_PIECES : defaultPieces,
              showNotation: prefs.show_coordinates,
              animationDurationInMs: 180,
            }}
          />
        </div>

        {pending && (
          <div className="promotion" role="dialog" aria-label="Choose a promotion piece">
            <p>Promote to</p>
            <div className="promotion-choices">
              {PROMOTION_PIECES.map(({ code, label: pieceLabel }) => (
                <button
                  key={code}
                  type="button"
                  className="promotion-choice"
                  onClick={() => {
                    setPromotion(null);
                    onMove?.(`${pending.from}${pending.to}${code}`);
                  }}
                >
                  {pieceLabel}
                </button>
              ))}
            </div>
            <button type="button" className="link-button" onClick={() => setPromotion(null)}>
              Cancel
            </button>
          </div>
        )}
      </div>

      {interactive && (
        <form className="typed-move" onSubmit={submitTyped}>
          <label htmlFor={`typed-${id}`}>Type a move</label>
          <input
            id={`typed-${id}`}
            value={typed}
            onChange={(event) => {
              setTyped(event.target.value);
              setTypedError('');
            }}
            placeholder="e.g. Nf3 or g1f3"
            autoComplete="off"
            spellCheck="false"
          />
          <button type="submit" className="btn btn-secondary btn-sm">
            Play
          </button>
          {typedError && (
            <p className="form-error" role="alert">
              {typedError}
            </p>
          )}
        </form>
      )}
    </div>
  );
}
