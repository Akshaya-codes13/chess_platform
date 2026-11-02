export const FILES = 'abcdefgh';

const PIECE_NAMES = { k: 'king', q: 'queen', r: 'rook', b: 'bishop', n: 'knight', p: 'pawn' };

// Solid glyphs for both colours (styled per colour in CSS); U+FE0E keeps the
// pawn from rendering as an emoji on some platforms.
const GLYPHS = { k: '♚', q: '♛', r: '♜', b: '♝', n: '♞', p: '♟' };

/** Parse a FEN into { pieces: { e4: { color, type } }, turn, fullmove }. */
export function parseFen(fen) {
  const [placement = '', turn = 'w', , , , fullmove = '1'] = (fen || '').split(' ');
  const pieces = {};

  placement.split('/').forEach((row, rowIndex) => {
    let file = 0;
    for (const char of row) {
      if (/\d/.test(char)) {
        file += Number(char);
      } else {
        const square = `${FILES[file]}${8 - rowIndex}`;
        pieces[square] = {
          color: char === char.toUpperCase() ? 'white' : 'black',
          type: char.toLowerCase(),
        };
        file += 1;
      }
    }
  });

  return { pieces, turn: turn === 'b' ? 'black' : 'white', fullmove: Number(fullmove) || 1 };
}

export function pieceGlyph(piece) {
  return `${GLYPHS[piece.type]}︎`;
}

export function pieceName(piece) {
  return `${piece.color} ${PIECE_NAMES[piece.type]}`;
}

/** Square of the side-to-move's king, for highlighting check. */
export function kingSquare(pieces, color) {
  return (
    Object.keys(pieces).find((sq) => pieces[sq].type === 'k' && pieces[sq].color === color) ?? null
  );
}

export const PROMOTION_PIECES = [
  { code: 'q', label: 'Queen' },
  { code: 'r', label: 'Rook' },
  { code: 'b', label: 'Bishop' },
  { code: 'n', label: 'Knight' },
];
