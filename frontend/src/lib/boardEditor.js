// Pure helpers for the board editor: build a FEN from a placement map and
// explain why a position is not legal.
import { Chess, validateFen } from 'chess.js';

export const EMPTY_FEN = '8/8/8/8/8/8/8/8 w - - 0 1';
export const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

const FILES = 'abcdefgh';

/** { e4: 'wP', … } -> FEN placement field. */
export function placementToFen(placement) {
  const rows = [];
  for (let rank = 8; rank >= 1; rank -= 1) {
    let row = '';
    let empty = 0;
    for (const file of FILES) {
      const piece = placement[`${file}${rank}`];
      if (!piece) {
        empty += 1;
        continue;
      }
      if (empty) row += empty;
      empty = 0;
      row += piece[0] === 'w' ? piece[1].toUpperCase() : piece[1].toLowerCase();
    }
    rows.push(row + (empty ? empty : ''));
  }
  return rows.join('/');
}

/** FEN -> { e4: 'wP', … }. */
export function fenToPlacement(fen) {
  const placement = {};
  fen
    .split(' ')[0]
    .split('/')
    .forEach((row, index) => {
      let file = 0;
      for (const char of row) {
        if (/\d/.test(char)) {
          file += Number(char);
        } else {
          const color = char === char.toUpperCase() ? 'w' : 'b';
          placement[`${FILES[file]}${8 - index}`] = `${color}${char.toUpperCase()}`;
          file += 1;
        }
      }
    });
  return placement;
}

/** Castling rights that the placement still allows. */
export function possibleCastling(placement, wanted = 'KQkq') {
  const has = (square, piece) => placement[square] === piece;
  const rights = [];
  if (wanted.includes('K') && has('e1', 'wK') && has('h1', 'wR')) rights.push('K');
  if (wanted.includes('Q') && has('e1', 'wK') && has('a1', 'wR')) rights.push('Q');
  if (wanted.includes('k') && has('e8', 'bK') && has('h8', 'bR')) rights.push('k');
  if (wanted.includes('q') && has('e8', 'bK') && has('a8', 'bR')) rights.push('q');
  return rights.join('') || '-';
}

export function buildFen(placement, { turn = 'w', castling = 'KQkq' } = {}) {
  return `${placementToFen(placement)} ${turn} ${possibleCastling(placement, castling)} - 0 1`;
}

/** Return null when `fen` is a playable position, otherwise a reason. */
export function positionProblem(fen) {
  const placement = fenToPlacement(fen);
  const pieces = Object.entries(placement);
  const count = (piece) => pieces.filter(([, p]) => p === piece).length;

  if (count('wK') !== 1 || count('bK') !== 1) return 'Each side needs exactly one king.';
  if (pieces.some(([square, p]) => p[1] === 'P' && /[18]$/.test(square)))
    return 'Pawns cannot stand on the first or last rank.';

  const check = validateFen(fen);
  if (!check.ok) return check.error;

  const game = new Chess(fen);
  // The side that just moved cannot be in check.
  const other = fen.split(' ')[1] === 'w' ? 'b' : 'w';
  const flipped = fen.replace(/ [wb] /, ` ${other} `);
  try {
    if (new Chess(flipped, { skipValidation: true }).inCheck()) {
      return 'The side not to move is in check.';
    }
  } catch {
    // An unusual FEN chess.js cannot flip; the forward check below still runs.
  }
  return game.isGameOver() && !game.isCheckmate() && !game.isStalemate()
    ? 'This position is already drawn.'
    : null;
}
