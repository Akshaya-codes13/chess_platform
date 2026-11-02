/**
 * Moves in standard numbered pairs. `moves` are { san, by } in play order;
 * `startTurn` and `startNumber` come from the starting FEN. Clicking a move
 * calls onSelect with the number of half-moves played up to it.
 */
export default function MoveList({
  moves,
  startTurn = 'white',
  startNumber = 1,
  current,
  onSelect,
}) {
  if (!moves.length) return <p className="move-list-empty">Your moves will appear here.</p>;

  const rows = [];
  let number = startNumber;
  let index = 0;

  if (startTurn === 'black') {
    rows.push({ number, white: null, black: { ...moves[0], ply: 1 } });
    number += 1;
    index = 1;
  }

  for (; index < moves.length; index += 2) {
    rows.push({
      number,
      white: { ...moves[index], ply: index + 1 },
      black: moves[index + 1] ? { ...moves[index + 1], ply: index + 2 } : null,
    });
    number += 1;
  }

  const cell = (move) =>
    move ? (
      <button
        type="button"
        className={`move ${move.by === 'opponent' ? 'is-reply' : ''} ${current === move.ply ? 'is-current' : ''}`}
        aria-current={current === move.ply ? 'step' : undefined}
        onClick={() => onSelect?.(move.ply)}
      >
        {move.san}
      </button>
    ) : (
      <span className="move-gap">…</span>
    );

  return (
    <ol className="move-list" aria-label="Move history">
      {rows.map((row) => (
        <li key={row.number} className="move-row">
          <span className="move-number">{row.number}.</span>
          {cell(row.white)}
          {cell(row.black)}
        </li>
      ))}
    </ol>
  );
}
