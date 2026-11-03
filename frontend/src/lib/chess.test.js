import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  buildFen,
  EMPTY_FEN,
  fenToPlacement,
  placementToFen,
  positionProblem,
  possibleCastling,
  START_FEN,
} from './boardEditor.js';
import { boardColors, glyphPieceList } from './boardThemes.js';
import { formatScore, parseInfo, whitePercent } from './uci.js';

test('placement and FEN round-trip', () => {
  const placement = fenToPlacement(START_FEN);
  assert.equal(placement.e1, 'wK');
  assert.equal(placement.d8, 'bQ');
  assert.equal(Object.keys(placement).length, 32);
  assert.equal(placementToFen(placement), START_FEN.split(' ')[0]);
  assert.equal(placementToFen({}), EMPTY_FEN.split(' ')[0]);
});

test('castling rights follow the pieces on the board', () => {
  const placement = fenToPlacement(START_FEN);
  assert.equal(possibleCastling(placement), 'KQkq');
  delete placement.h1;
  assert.equal(possibleCastling(placement), 'Qkq');
  assert.equal(possibleCastling({}), '-');
  assert.equal(buildFen({ e1: 'wK', e8: 'bK' }, { turn: 'b' }), '4k3/8/8/8/8/8/8/4K3 b - - 0 1');
});

test('positionProblem explains illegal positions', () => {
  assert.equal(positionProblem(START_FEN), null);
  assert.match(positionProblem(EMPTY_FEN), /one king/);
  assert.match(positionProblem('4k3/8/8/8/8/8/8/P3K3 w - - 0 1'), /first or last rank/);
  // White to move while Black is in check from the rook.
  assert.match(positionProblem('4k3/8/8/8/8/8/8/4RK2 w - - 0 1'), /not to move is in check/);
  assert.equal(positionProblem('4k3/8/8/8/8/8/8/4RK2 b - - 0 1'), null);
});

test('parseInfo normalises scores to White', () => {
  const line = 'info depth 18 seldepth 24 multipv 1 score cp 35 nodes 1 pv e2e4 e7e5 g1f3';
  assert.deepEqual(parseInfo(line, 'w'), {
    depth: 18,
    multipv: 1,
    score: { cp: 35 },
    pv: ['e2e4', 'e7e5', 'g1f3'],
  });
  assert.deepEqual(parseInfo(line, 'b').score, { cp: -35 });
  assert.deepEqual(parseInfo('info depth 5 score mate 2 pv h5f7', 'b').score, { mate: -2 });
  assert.equal(parseInfo('info string NNUE enabled', 'w'), null);
  assert.equal(parseInfo('bestmove e2e4', 'w'), null);
});

test('score formatting and evaluation bar', () => {
  assert.equal(formatScore({ cp: 125 }), '+1.25');
  assert.equal(formatScore({ cp: -40 }), '-0.40');
  assert.equal(formatScore({ mate: 3 }), '#3');
  assert.equal(whitePercent({ cp: 0 }), 50);
  assert.equal(whitePercent({ mate: -1 }), 0);
  assert.ok(whitePercent({ cp: 400 }) > 85);
});

test('board themes and glyph pieces', () => {
  assert.equal(boardColors('nope'), boardColors('wood'));
  assert.equal(glyphPieceList().length, 12);
  assert.ok(glyphPieceList().some((piece) => piece.code === 'bN'));
});
