// Helpers for talking UCI to the browser Stockfish engine.

/**
 * Parse an engine "info" line. Returns null for lines without a score or PV.
 * Scores are from the side to move; `whiteScore` normalises them to White.
 */
export function parseInfo(line, sideToMove = 'w') {
  if (!line.startsWith('info ') || !line.includes(' pv ')) return null;

  const depth = Number(line.match(/ depth (\d+)/)?.[1] ?? 0);
  const multipv = Number(line.match(/ multipv (\d+)/)?.[1] ?? 1);
  const cp = line.match(/ score cp (-?\d+)/);
  const mate = line.match(/ score mate (-?\d+)/);
  const pv = line.split(' pv ')[1]?.trim().split(/\s+/) ?? [];

  if (!cp && !mate) return null;

  const sign = sideToMove === 'w' ? 1 : -1;
  const score = mate ? { mate: Number(mate[1]) * sign } : { cp: Number(cp[1]) * sign };

  return { depth, multipv, score, pv };
}

/** "+1.25", "-0.40", "#3", "#-2" from White's point of view. */
export function formatScore(score) {
  if (!score) return '';
  if (score.mate !== undefined) return `#${score.mate}`;
  const pawns = score.cp / 100;
  return `${pawns > 0 ? '+' : ''}${pawns.toFixed(2)}`;
}

/** Evaluation bar fill for White, 0–100. */
export function whitePercent(score) {
  if (!score) return 50;
  if (score.mate !== undefined) return score.mate > 0 ? 100 : 0;
  // Logistic curve similar to common GUIs: ±4 pawns ≈ 90/10.
  return Math.round(100 / (1 + Math.exp(-score.cp / 180)));
}
