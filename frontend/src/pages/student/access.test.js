import assert from 'node:assert/strict';
import { test } from 'node:test';
import { accessReducer, initialAccess } from './access.js';

const AT = new Date('2026-11-02T10:00:00Z');
const TRAINER = { id: 't1', full_name: 'Demo Trainer' };

function run(...actions) {
  return actions.reduce(accessReducer, initialAccess);
}

test('starts by checking', () => {
  assert.equal(initialAccess.phase, 'checking');
  assert.equal(initialAccess.checking, true);
});

test('existing student with a trainer goes straight to the portal', () => {
  const state = run({ type: 'loaded', body: { status: 'ready', trainer: TRAINER }, at: AT });

  assert.equal(state.phase, 'ready');
  assert.deepEqual(state.trainer, TRAINER);
  // Not a fresh assignment, so the gate does not redirect.
  assert.equal(state.justAssigned, false);
});

test('student without a trainer sees the waiting screen', () => {
  const state = run({
    type: 'loaded',
    body: { status: 'awaiting_trainer', trainer: null },
    at: AT,
  });

  assert.equal(state.phase, 'waiting');
  assert.equal(state.checking, false);
  assert.equal(state.checkedAt, AT);
});

test('unknown or missing status is treated as waiting, never ready', () => {
  assert.equal(run({ type: 'loaded', body: { status: 'weird' }, at: AT }).phase, 'waiting');
  assert.equal(run({ type: 'loaded', body: null, at: AT }).phase, 'waiting');
});

test('re-checking after assignment opens the portal and flags the transition', () => {
  const later = new Date('2026-11-02T10:05:00Z');
  const state = run(
    { type: 'loaded', body: { status: 'awaiting_trainer' }, at: AT },
    { type: 'check' },
    { type: 'loaded', body: { status: 'ready', trainer: TRAINER }, at: later },
  );

  assert.equal(state.phase, 'ready');
  assert.equal(state.justAssigned, true);
  assert.equal(state.checkedAt, later);
});

test('re-checking while still unassigned stays on the waiting screen', () => {
  const state = run(
    { type: 'loaded', body: { status: 'awaiting_trainer' }, at: AT },
    { type: 'check' },
  );
  assert.equal(state.checking, true);
  assert.equal(state.phase, 'waiting');

  const after = accessReducer(state, {
    type: 'loaded',
    body: { status: 'awaiting_trainer' },
    at: AT,
  });
  assert.equal(after.phase, 'waiting');
  assert.equal(after.justAssigned, false);
});

test('a failed first check shows an error; a failed re-check keeps waiting', () => {
  const first = run({ type: 'failed', message: 'Offline' });
  assert.equal(first.phase, 'error');
  assert.equal(first.error, 'Offline');

  const recheck = run(
    { type: 'loaded', body: { status: 'awaiting_trainer' }, at: AT },
    { type: 'check' },
    { type: 'failed' },
  );
  assert.equal(recheck.phase, 'waiting');
  assert.equal(recheck.error, 'Could not reach the academy server.');
  assert.equal(recheck.checking, false);
});

test('a new check clears the previous error', () => {
  const state = run({ type: 'failed', message: 'Offline' }, { type: 'check' });
  assert.equal(state.error, null);
  assert.equal(state.checking, true);
});
