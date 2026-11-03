import { useEffect, useRef, useState } from 'react';
import { api } from '../../api/client';
import ChessBoard from '../../components/chess/ChessBoard';
import MoveList from '../../components/chess/MoveList';
import Button from '../../components/ui/Button';
import LoadState from '../../components/ui/LoadState';
import PageHeader from '../../components/ui/PageHeader';
import ProgressBar from '../../components/ui/ProgressBar';
import StatusBadge from '../../components/ui/StatusBadge';
import { useApi } from '../../hooks/useApi';
import { titleCase } from '../../lib/format';
import { parseFen } from '../../lib/fen';
import { useRoute } from '../../routes/router';

const REPLY_DELAY_MS = 450;

export default function PuzzlePage() {
  const { params } = useRoute();
  const { assignmentId, puzzleId } = params;
  const { data, error, loading, reload } = useApi(`/student/puzzles/${puzzleId}`, {
    query: { assignment_id: assignmentId },
  });

  if (loading || error) return <LoadState loading={loading} error={error} onRetry={reload} />;

  return <PuzzleSolver key={data.id} puzzle={data} />;
}

function freshGame(puzzle) {
  return {
    moves: [],
    history: [],
    position: puzzle.position,
    status: 'playing', // playing | checking | replying | solved | failed
    result: null,
    error: '',
    viewPly: null,
    startedAt: Date.now(),
    hintsUsed: 0,
    // The latest hint, valid only for the position after `moves`.
    hint: null,
  };
}

function PuzzleSolver({ puzzle }) {
  const [game, setGame] = useState(() => freshGame(puzzle));
  const [showSolution, setShowSolution] = useState(false);
  const replyTimer = useRef(null);
  const { turn: startTurn, fullmove } = parseFen(puzzle.position.fen);
  const assignmentPath = `/student/assignments/${puzzle.assignment_id}`;
  const puzzlePath = (id) => `${assignmentPath}/puzzles/${id}`;

  useEffect(() => () => clearTimeout(replyTimer.current), []);

  const livePly = game.history.length;
  const reviewing = game.viewPly !== null && game.viewPly !== livePly;
  const shownPly = reviewing ? game.viewPly : livePly;
  const boardFen = shownPly === 0 ? puzzle.position.fen : game.history[shownPly - 1].fen;
  const shownMove = shownPly > 0 ? game.history[shownPly - 1] : null;
  const canMove = game.status === 'playing' && !reviewing && !puzzle.assignment_closed;
  const studentMovesPlayed = game.moves.length;

  async function play(uci) {
    const moves = [...game.moves, uci];
    setGame((g) => ({ ...g, status: 'checking', error: '', viewPly: null, hint: null }));

    try {
      const result = await api(`/student/puzzles/${puzzle.id}/attempts`, {
        method: 'POST',
        body: {
          assignment_id: puzzle.assignment_id,
          moves,
          time_taken_seconds: Math.min(86400, Math.round((Date.now() - game.startedAt) / 1000)),
          hints_used: game.hintsUsed,
        },
      });
      const nextStatus = result.status === 'in_progress' ? 'playing' : result.status;
      const finish = (g) => ({
        ...g,
        moves,
        history: result.played,
        position: result.position,
        status: nextStatus,
        result,
      });

      if (result.played.at(-1)?.by === 'opponent') {
        // Show the student's move first, then the opponent's reply.
        setGame((g) => ({ ...g, moves, history: result.played.slice(0, -1), status: 'replying' }));
        replyTimer.current = setTimeout(() => setGame(finish), REPLY_DELAY_MS);
      } else {
        setGame(finish);
      }
    } catch (err) {
      setGame((g) => ({
        ...g,
        status: 'playing',
        error: err.message || 'The move could not be checked.',
      }));
    }
  }

  function restart() {
    clearTimeout(replyTimer.current);
    setShowSolution(false);
    setGame(freshGame(puzzle));
  }

  async function askHint() {
    // First hint: which piece moves. Asking again reveals the move.
    const level = game.hint ? 2 : 1;
    try {
      const hint = await api(`/student/puzzles/${puzzle.id}/hint`, {
        method: 'POST',
        body: { assignment_id: puzzle.assignment_id, moves: game.moves, level },
      });
      setGame((g) => ({ ...g, hint, hintsUsed: g.hintsUsed + 1, error: '' }));
    } catch (err) {
      setGame((g) => ({ ...g, error: err.message || 'No hint is available right now.' }));
    }
  }

  const hintShown = game.hint && game.status === 'playing' && !reviewing ? game.hint : null;

  function review(ply) {
    setGame((g) => ({ ...g, viewPly: Math.max(0, Math.min(livePly, ply)) }));
  }

  const subtitle = [
    `Puzzle ${puzzle.display_order} of ${puzzle.total_in_assignment}`,
    puzzle.rating && `rating ${puzzle.rating}`,
    puzzle.difficulty && titleCase(puzzle.difficulty),
  ]
    .filter(Boolean)
    .join(' · ');

  return (
    <div className="page puzzle-page">
      <PageHeader
        back={{ to: assignmentPath, label: puzzle.assignment_title }}
        title="Find the best move"
        subtitle={subtitle}
      />

      <div className="puzzle-layout">
        <div className="puzzle-board">
          <ChessBoard
            fen={boardFen}
            orientation={puzzle.orientation}
            legalMoves={canMove ? game.position.legal_moves : []}
            onMove={play}
            lastMove={
              shownMove ? { from: shownMove.uci.slice(0, 2), to: shownMove.uci.slice(2, 4) } : null
            }
            interactive={canMove}
            inCheck={!reviewing && game.position.is_check}
            highlights={
              hintShown
                ? { [hintShown.from_square]: { boxShadow: 'inset 0 0 0 4px var(--color-reward)' } }
                : {}
            }
            arrows={
              hintShown?.move
                ? [
                    {
                      startSquare: hintShown.move.slice(0, 2),
                      endSquare: hintShown.move.slice(2, 4),
                      color: 'rgba(183, 131, 47, 0.85)',
                    },
                  ]
                : []
            }
            label="Puzzle board"
          />
          <div className="board-controls" role="group" aria-label="Review moves">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => review(0)}
              disabled={shownPly === 0}
              aria-label="First position"
            >
              ⏮
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => review(shownPly - 1)}
              disabled={shownPly === 0}
              aria-label="Previous move"
            >
              ◀
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => review(shownPly + 1)}
              disabled={!reviewing}
              aria-label="Next move"
            >
              ▶
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => review(livePly)}
              disabled={!reviewing}
              aria-label="Current position"
            >
              ⏭
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={restart}
              disabled={game.status === 'checking'}
            >
              Restart
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={askHint}
              disabled={!canMove || game.hint?.move != null}
            >
              {game.hint ? 'Show the move' : 'Hint'}
            </Button>
          </div>
          {hintShown && (
            <p className="hint-text" role="status">
              {hintShown.move
                ? `Play ${hintShown.san}.`
                : `Move your ${hintShown.piece ?? 'piece'} on ${hintShown.from_square}.`}{' '}
              Hints used: {game.hintsUsed}. Your trainer sees how many hints you used.
            </p>
          )}
        </div>

        <aside className="puzzle-panel">
          <PuzzleStatus
            puzzle={puzzle}
            game={game}
            reviewing={reviewing}
            studentMovesPlayed={studentMovesPlayed}
          />

          {game.error && (
            <p className="form-error" role="alert">
              {game.error}
            </p>
          )}

          {(game.status === 'solved' || game.status === 'failed') && (
            <AttemptResult
              result={game.result}
              puzzle={puzzle}
              onRetry={restart}
              nextPath={puzzle.next_puzzle_id ? puzzlePath(puzzle.next_puzzle_id) : null}
              assignmentPath={assignmentPath}
            />
          )}

          <section className="panel-section">
            <h2 className="panel-heading">Moves</h2>
            <MoveList
              moves={game.history}
              startTurn={startTurn}
              startNumber={fullmove}
              current={shownPly}
              onSelect={review}
            />
            <p className="hint">
              A wrong move ends the attempt, so moves cannot be taken back. Use the arrows to
              review, or restart.
            </p>
          </section>

          {puzzle.status === 'solved' && game.status !== 'solved' && (
            <section className="panel-section">
              <p className="row-meta">
                You have solved this puzzle before. Solving it again is good practice but earns no
                XP.
              </p>
              {showSolution ? (
                <SolutionLine
                  sans={puzzle.solution_san}
                  startTurn={startTurn}
                  startNumber={fullmove}
                  explanation={puzzle.explanation}
                />
              ) : (
                <Button variant="ghost" size="sm" onClick={() => setShowSolution(true)}>
                  Show the solution
                </Button>
              )}
            </section>
          )}

          {puzzle.themes.length > 0 && (
            <p className="row-meta">Themes: {puzzle.themes.join(', ')}</p>
          )}

          <nav className="puzzle-nav" aria-label="Other puzzles in this assignment">
            {puzzle.previous_puzzle_id ? (
              <Button variant="ghost" size="sm" to={puzzlePath(puzzle.previous_puzzle_id)}>
                Previous puzzle
              </Button>
            ) : (
              <span />
            )}
            {puzzle.next_puzzle_id && (
              <Button variant="ghost" size="sm" to={puzzlePath(puzzle.next_puzzle_id)}>
                Next puzzle
              </Button>
            )}
          </nav>
        </aside>
      </div>
    </div>
  );
}

function PuzzleStatus({ puzzle, game, reviewing, studentMovesPlayed }) {
  let text;
  if (puzzle.assignment_closed)
    text = 'This assignment is closed. You can look at the position, but moves are not accepted.';
  else if (reviewing) text = 'Reviewing an earlier position.';
  else if (game.status === 'checking') text = 'Checking your move…';
  else if (game.status === 'replying') text = 'Correct. Your opponent replies…';
  else if (game.status === 'solved') text = 'Solved.';
  else if (game.status === 'failed') text = 'That was not the winning move.';
  else if (game.position.is_checkmate) text = 'Checkmate.';
  else if (studentMovesPlayed === 0) {
    text = `${titleCase(puzzle.orientation)} to move. ${
      puzzle.moves_required === 1
        ? 'Find the winning move.'
        : `Find the best line — ${puzzle.moves_required} moves.`
    }`;
  } else {
    const last = game.history.at(-1);
    text = `Good. ${last?.by === 'opponent' ? `Your opponent played ${last.san}. ` : ''}Move ${studentMovesPlayed + 1} of ${puzzle.moves_required}.`;
  }

  return (
    <div className={`puzzle-status is-${game.status}`} aria-live="polite">
      <span className={`turn-dot is-${puzzle.orientation}`} aria-hidden="true" />
      <p>{text}</p>
      {game.position.is_check && !game.position.is_checkmate && !reviewing && (
        <span className="row-meta">Check</span>
      )}
    </div>
  );
}

function SolutionLine({ sans, startTurn, startNumber, explanation }) {
  return (
    <div className="solution">
      <MoveList
        moves={sans.map((san, i) => ({ san, by: i % 2 ? 'opponent' : 'student' }))}
        startTurn={startTurn}
        startNumber={startNumber}
      />
      {explanation && <p className="prose">{explanation}</p>}
    </div>
  );
}

function AttemptResult({ result, puzzle, onRetry, nextPath, assignmentPath }) {
  const { turn, fullmove } = parseFen(puzzle.position.fen);
  const progress = result.assignment_progress;

  if (result.status === 'failed') {
    const wrong = result.played.at(-1);
    return (
      <section className="result is-failed" aria-labelledby="result-title">
        <h2 id="result-title">Not this time</h2>
        <p>
          {wrong ? `${wrong.san} is not the solution.` : 'That move is not the solution.'} The
          attempt has been recorded — look at the position again and try another idea.
        </p>
        <div className="result-actions">
          <Button onClick={onRetry}>Try again</Button>
          <Button variant="ghost" to={assignmentPath}>
            Back to assignment
          </Button>
        </div>
      </section>
    );
  }

  return (
    <section className="result is-solved" aria-labelledby="result-title">
      <h2 id="result-title">Puzzle solved</h2>
      {result.xp_awarded > 0 ? (
        <p className="xp-award">+{result.xp_awarded} XP</p>
      ) : (
        <p className="row-meta">
          {result.already_solved
            ? 'You had already solved this puzzle, so no XP this time.'
            : 'No XP for this solve.'}
        </p>
      )}

      {result.badges_awarded.length > 0 && (
        <ul className="badge-awards">
          {result.badges_awarded.map((badge) => (
            <li key={badge.code}>
              New badge: <strong>{badge.name}</strong>
              {badge.xp_reward ? ` (+${badge.xp_reward} XP)` : ''}
            </li>
          ))}
        </ul>
      )}

      {result.solution_san && (
        <SolutionLine
          sans={result.solution_san}
          startTurn={turn}
          startNumber={fullmove}
          explanation={result.explanation}
        />
      )}

      <div className="result-progress">
        <ProgressBar
          value={progress.completion_percent}
          label={`${progress.completed_puzzles} of ${progress.total_puzzles} solved in this assignment`}
          tone={result.assignment_status === 'completed' ? 'success' : 'default'}
        />
        {result.assignment_completed_now && (
          <p>
            <StatusBadge status="completed" /> Assignment complete — it has been submitted to your
            trainer.
          </p>
        )}
      </div>

      <div className="result-actions">
        {nextPath ? (
          <Button to={nextPath}>Next puzzle</Button>
        ) : (
          <Button to={assignmentPath}>Back to assignment</Button>
        )}
        <Button variant="ghost" onClick={onRetry}>
          Solve again
        </Button>
      </div>
    </section>
  );
}
