import { Chess } from 'chess.js';
import { useState } from 'react';
import { errorMessage, trainerApi } from '../../features/trainer/api';
import { SelectField, TextArea, TextField } from '../../features/trainer/components/Field';
import FenBoard from '../../features/trainer/components/FenBoard';
import TrainerPage from '../../features/trainer/components/TrainerPage';
import { toast } from '../../features/trainer/components/toastStore';
import { Button, Loaded, PageHeader, Section, Status } from '../../features/trainer/components/ui';
import { formatDateTime } from '../../features/trainer/format';
import { useLoader } from '../../features/trainer/hooks';
import { useRoute } from '../../routes/router';

/** UCI moves played from `fen` as SAN, falling back to UCI if unreadable. */
function toSan(fen, moves) {
  const game = new Chess(fen);
  return moves.map((uci) => {
    try {
      return game.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] }).san;
    } catch {
      return uci;
    }
  });
}

export default function SubmissionReviewPage() {
  const { params } = useRoute();
  const result = useLoader(
    () => trainerApi.submission(params.assignmentId, params.studentId),
    [params.assignmentId, params.studentId],
  );

  return (
    <TrainerPage>
      <Loaded result={result}>
        {(data) => (
          <>
            <PageHeader
              back={{
                to: `/trainer/assignments/${data.assignment_id}`,
                label: data.assignment_title,
              }}
              title={data.full_name}
              subtitle={`${data.earned_points} of ${data.total_points} points from solved puzzles`}
            />
            <ReviewForm data={data} onSaved={result.reload} />
            <Section title="Attempts">
              <div className="review-puzzles">
                {data.puzzles.map((puzzle) => (
                  <article key={puzzle.puzzle_id} className="review-puzzle">
                    <FenBoard fen={puzzle.fen} size="sm" />
                    <div>
                      <h3 className="review-puzzle__title">
                        Puzzle {puzzle.display_order}
                        {puzzle.rating ? ` · ${puzzle.rating}` : ''} · {puzzle.points}{' '}
                        {puzzle.points === 1 ? 'point' : 'points'}{' '}
                        <Status
                          value={
                            puzzle.solved
                              ? 'completed'
                              : puzzle.attempts.length
                                ? 'in_progress'
                                : 'not_started'
                          }
                        />
                      </h3>
                      {puzzle.attempts.length === 0 ? (
                        <p className="tr-muted">Not attempted.</p>
                      ) : (
                        <ol className="review-attempts">
                          {puzzle.attempts.map((attempt) => (
                            <li key={attempt.id}>
                              <strong>{attempt.is_solved ? 'Solved' : 'Failed'}</strong> ·{' '}
                              {toSan(puzzle.fen, attempt.moves).join(' ') || '—'}
                              <span className="tr-muted">
                                {' '}
                                · {formatDateTime(attempt.attempted_at)}
                                {attempt.time_taken_seconds != null
                                  ? ` · ${attempt.time_taken_seconds}s`
                                  : ''}
                                {attempt.hints_used
                                  ? ` · ${attempt.hints_used} hint${attempt.hints_used === 1 ? '' : 's'}`
                                  : ''}
                              </span>
                            </li>
                          ))}
                        </ol>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            </Section>
          </>
        )}
      </Loaded>
    </TrainerPage>
  );
}

function ReviewForm({ data, onSaved }) {
  const submission = data.submission;
  const [form, setForm] = useState({
    status: 'graded',
    score: String(submission?.score ?? data.earned_points),
    feedback: submission?.trainer_feedback ?? '',
  });
  const [busy, setBusy] = useState(false);

  if (!submission) {
    return (
      <Section title="Submission">
        <p className="tr-muted">
          Not submitted yet. Students submit when they finish every puzzle, or hand in partial work
          themselves.
        </p>
      </Section>
    );
  }

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    try {
      await trainerApi.reviewSubmission(data.assignment_id, data.student_id, {
        status: form.status,
        score: form.score === '' ? null : Number(form.score),
        feedback: form.feedback.trim() || null,
      });
      toast.success(form.status === 'graded' ? 'Submission graded.' : 'Returned to the student.');
      onSaved();
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section
      title={`Submission ${submission.attempt_number}`}
      actions={
        <Status
          value={
            submission.status === 'graded'
              ? 'completed'
              : submission.status === 'returned'
                ? 'late'
                : 'scheduled'
          }
        />
      }
    >
      <p className="tr-muted">
        Submitted {formatDateTime(submission.submitted_at)} · status {submission.status}
      </p>
      <form className="tr-form" onSubmit={submit}>
        <div className="tr-form-grid">
          <SelectField
            label="Decision"
            value={form.status}
            onChange={(status) => setForm({ ...form, status })}
            options={[
              { value: 'graded', label: 'Grade (accept)' },
              { value: 'returned', label: 'Return for more work' },
            ]}
          />
          <TextField
            label={`Score (0–${data.total_points})`}
            type="number"
            min={0}
            max={data.total_points}
            value={form.score}
            onChange={(score) => setForm({ ...form, score })}
          />
        </div>
        <TextArea
          label="Feedback for the student"
          rows={4}
          maxLength={5000}
          value={form.feedback}
          onChange={(feedback) => setForm({ ...form, feedback })}
        />
        <div>
          <Button type="submit" disabled={busy}>
            {busy ? 'Saving…' : 'Save review'}
          </Button>
        </div>
      </form>
    </Section>
  );
}
