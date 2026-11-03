// Copy the browser Stockfish engine (lite, single-threaded) into public/ so
// Vite serves the worker script and its .wasm side by side, which the
// engine requires. Runs before `dev` and `build`; the copies are git-ignored.
import { copyFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const source = join(root, 'node_modules', 'stockfish', 'bin');
const target = join(root, 'public', 'stockfish');

mkdirSync(target, { recursive: true });
for (const file of ['stockfish-19-lite-single.js', 'stockfish-19-lite-single.wasm']) {
  copyFileSync(join(source, file), join(target, file));
}
