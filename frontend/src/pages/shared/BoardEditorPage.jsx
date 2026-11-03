import { useState } from 'react';
import { Chessboard, defaultPieces } from 'react-chessboard';
import EnginePanel from '../../components/chess/EnginePanel';
import TrainerPage from '../../features/trainer/components/TrainerPage';
import { toast } from '../../features/trainer/components/toastStore';
import { Button, ButtonLink, PageHeader, Section } from '../../features/trainer/components/ui';
import {
  buildFen,
  EMPTY_FEN,
  fenToPlacement,
  positionProblem,
  START_FEN,
} from '../../lib/boardEditor';
import { boardColors } from '../../lib/boardThemes';
import { useRoute } from '../../routes/router';
import { useBoardPrefs } from '../../store/preferencesStore';
import { useRole } from './base';

const PALETTE = ['K', 'Q', 'R', 'B', 'N', 'P'];
const PIECE_NAMES = { K: 'king', Q: 'queen', R: 'rook', B: 'bishop', N: 'knight', P: 'pawn' };

function initialState(fen) {
  const source = fen && fen.split(' ').length >= 2 ? fen : START_FEN;
  const [, turn = 'w', castling = 'KQkq'] = source.split(' ');
  return { placement: fenToPlacement(source), turn, castling: castling === '-' ? '' : castling };
}

/**
 * Set up any position: pick a piece (or the eraser) and click squares, or
 * drag pieces around. The FEN updates live and is checked for legality;
 * legal positions can be analysed or turned into a puzzle.
 */
export default function BoardEditorPage() {
  const { query } = useRoute();
  const role = useRole();
  const prefs = useBoardPrefs();
  const colors = boardColors(prefs.theme);
  const [state, setState] = useState(() => initialState(query.fen));
  const [tool, setTool] = useState('wQ');
  const [flipped, setFlipped] = useState(false);
  const [fenInput, setFenInput] = useState('');
  const [bestMove, setBestMove] = useState(null);

  const fen = buildFen(state.placement, { turn: state.turn, castling: state.castling || '-' });
  const problem = positionProblem(fen);

  function setPlacement(update) {
    setState((current) => ({ ...current, placement: update(current.placement) }));
  }

  function onSquareClick({ square }) {
    setPlacement((placement) => {
      const next = { ...placement };
      if (tool === 'erase' || next[square] === tool) delete next[square];
      else next[square] = tool;
      return next;
    });
  }

  function onPieceDrop({ piece, sourceSquare, targetSquare }) {
    setPlacement((placement) => {
      const next = { ...placement };
      delete next[sourceSquare];
      // Dropping off the board removes the piece.
      if (targetSquare) next[targetSquare] = piece.pieceType;
      return next;
    });
    return true;
  }

  function loadFen(event) {
    event.preventDefault();
    const text = fenInput.trim();
    const parts = text.split(/\s+/);
    if (parts[0]?.split('/').length !== 8) {
      toast.error('That does not look like a FEN.');
      return;
    }
    setState(initialState(parts.length === 1 ? `${text} w - - 0 1` : text));
    setFenInput('');
  }

  function toggleCastle(right) {
    setState((current) => ({
      ...current,
      castling: current.castling.includes(right)
        ? current.castling.replace(right, '')
        : 'KQkq'
            .split('')
            .filter((r) => r === right || current.castling.includes(r))
            .join(''),
    }));
  }

  return (
    <TrainerPage>
      <PageHeader
        title="Board editor"
        subtitle="Set up a position to study, analyse it with Stockfish, or turn it into a puzzle."
      />

      <div className="viewer-layout">
        <div className="viewer-board">
          <div className="chessboard" role="img" aria-label="Board editor">
            <Chessboard
              options={{
                id: 'board-editor',
                position: fen,
                boardOrientation: flipped ? 'black' : 'white',
                allowDragOffBoard: true,
                onSquareClick,
                onPieceDrop,
                lightSquareStyle: { backgroundColor: colors.light },
                darkSquareStyle: { backgroundColor: colors.dark },
                pieces: defaultPieces,
                showNotation: prefs.show_coordinates,
                arrows:
                  bestMove && !problem
                    ? [
                        {
                          startSquare: bestMove.slice(0, 2),
                          endSquare: bestMove.slice(2, 4),
                          color: 'rgba(63, 122, 74, 0.8)',
                        },
                      ]
                    : [],
              }}
            />
          </div>

          <div className="piece-palette" role="radiogroup" aria-label="Piece to place">
            {['w', 'b'].map((color) => (
              <div key={color} className="piece-palette__row">
                {PALETTE.map((type) => {
                  const code = `${color}${type}`;
                  const Piece = defaultPieces[code];
                  return (
                    <button
                      key={code}
                      type="button"
                      role="radio"
                      aria-checked={tool === code}
                      aria-label={`${color === 'w' ? 'White' : 'Black'} ${PIECE_NAMES[type]}`}
                      className={`palette-piece ${tool === code ? 'is-selected' : ''}`}
                      onClick={() => setTool(code)}
                    >
                      <Piece />
                    </button>
                  );
                })}
              </div>
            ))}
            <button
              type="button"
              role="radio"
              aria-checked={tool === 'erase'}
              className={`palette-piece palette-erase ${tool === 'erase' ? 'is-selected' : ''}`}
              onClick={() => setTool('erase')}
            >
              Erase
            </button>
          </div>
          <p className="tr-muted">
            Click a square to place the selected piece (click it again to remove it). Drag pieces to
            move them; drag a piece off the board to remove it.
          </p>
        </div>

        <aside className="viewer-panel">
          <Section title="Position">
            <div className="tr-page-actions">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setState(initialState(START_FEN))}
              >
                Start position
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setState({ ...initialState(EMPTY_FEN), castling: '' })}
              >
                Clear board
              </Button>
              <Button variant="secondary" size="sm" onClick={() => setFlipped((value) => !value)}>
                Flip
              </Button>
            </div>

            <fieldset className="editor-options">
              <legend>Side to move</legend>
              {[
                ['w', 'White'],
                ['b', 'Black'],
              ].map(([value, label]) => (
                <label key={value} className="tr-checkbox">
                  <input
                    type="radio"
                    name="turn"
                    checked={state.turn === value}
                    onChange={() => setState({ ...state, turn: value })}
                  />
                  <span>{label}</span>
                </label>
              ))}
            </fieldset>

            <fieldset className="editor-options">
              <legend>Castling rights</legend>
              {[
                ['K', 'White O-O'],
                ['Q', 'White O-O-O'],
                ['k', 'Black O-O'],
                ['q', 'Black O-O-O'],
              ].map(([right, label]) => (
                <label key={right} className="tr-checkbox">
                  <input
                    type="checkbox"
                    checked={state.castling.includes(right)}
                    onChange={() => toggleCastle(right)}
                  />
                  <span>{label}</span>
                </label>
              ))}
            </fieldset>

            <code className="tr-code fen-line">{fen}</code>
            {problem ? (
              <p className="tr-field__error" role="status">
                {problem}
              </p>
            ) : (
              <p className="tr-muted" role="status">
                Legal position.
              </p>
            )}

            <div className="tr-page-actions">
              <Button
                variant="secondary"
                size="sm"
                onClick={() =>
                  navigator.clipboard
                    ?.writeText(fen)
                    .then(() => toast.success('FEN copied.'))
                    .catch(() => toast.error('Copy failed.'))
                }
              >
                Copy FEN
              </Button>
              {role === 'trainer' && !problem && (
                <ButtonLink to={`/trainer/puzzles/new?fen=${encodeURIComponent(fen)}`} size="sm">
                  Create puzzle from position
                </ButtonLink>
              )}
            </div>

            <form className="tr-form" onSubmit={loadFen}>
              <label className="tr-field__label" htmlFor="fen-input">
                Load a FEN
              </label>
              <div className="tr-row">
                <input
                  id="fen-input"
                  className="tr-input tr-input--mono"
                  value={fenInput}
                  onChange={(event) => setFenInput(event.target.value)}
                  placeholder="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
                />
                <Button type="submit" size="sm">
                  Load
                </Button>
              </div>
            </form>
          </Section>

          {problem ? (
            <Section title="Stockfish">
              <p className="tr-muted">Fix the position to analyse it.</p>
            </Section>
          ) : (
            <EnginePanel fen={fen} onBestMove={setBestMove} />
          )}
        </aside>
      </div>
    </TrainerPage>
  );
}
