// Read-only board rendered from a FEN string, used for puzzle previews.
// Invalid FEN renders an empty board rather than throwing; validation
// itself is always done by the server.

const GLYPHS = {
  K: '♔',
  Q: '♕',
  R: '♖',
  B: '♗',
  N: '♘',
  P: '♙',
  k: '♚',
  q: '♛',
  r: '♜',
  b: '♝',
  n: '♞',
  p: '♟',
};
const NAMES = { k: 'king', q: 'queen', r: 'rook', b: 'bishop', n: 'knight', p: 'pawn' };
const FILES = 'abcdefgh';

function parsePlacement(fen) {
  const rows = (fen || '').split(' ')[0].split('/');
  if (rows.length !== 8) return null;
  const board = [];
  for (const row of rows) {
    const squares = [];
    for (const char of row) {
      if (/[1-8]/.test(char)) squares.push(...Array(Number(char)).fill(null));
      else if (GLYPHS[char]) squares.push(char);
      else return null;
    }
    if (squares.length !== 8) return null;
    board.push(squares);
  }
  return board;
}

export default function FenBoard({ fen, size = 'md', flipped = false }) {
  const board = parsePlacement(fen) || Array.from({ length: 8 }, () => Array(8).fill(null));
  const ranks = flipped ? [...board].reverse().map((row) => [...row].reverse()) : board;
  const turn = (fen || '').split(' ')[1] === 'b' ? 'Black' : 'White';

  return (
    <div
      className={`tr-board tr-board--${size}`}
      role="img"
      aria-label={`Chess position, ${turn} to move`}
    >
      {ranks.map((row, r) =>
        row.map((piece, f) => {
          const rank = flipped ? r + 1 : 8 - r;
          const file = FILES[flipped ? 7 - f : f];
          const dark = (r + f) % 2 === 1;
          return (
            <span
              key={`${file}${rank}`}
              className={`tr-board__sq ${dark ? 'tr-board__sq--dark' : 'tr-board__sq--light'}`}
              title={
                piece
                  ? `${piece === piece.toUpperCase() ? 'White' : 'Black'} ${NAMES[piece.toLowerCase()]} on ${file}${rank}`
                  : undefined
              }
            >
              {piece && (
                <span
                  className={`tr-board__piece ${piece === piece.toUpperCase() ? 'is-white' : 'is-black'}`}
                >
                  {GLYPHS[piece.toLowerCase()]}
                </span>
              )}
            </span>
          );
        }),
      )}
    </div>
  );
}
