import { useState } from 'react';
import { Link, navigate, useRoute } from '../../routes/router';
import { errorMessage, trainerApi } from '../../features/trainer/api';
import {
  formatDate,
  formatDateTime,
  formatPercent,
  sideToMove,
  titleCase,
} from '../../features/trainer/format';
import { useLoader } from '../../features/trainer/hooks';
import TrainerPage from '../../features/trainer/components/TrainerPage';
import ConfirmDialog from '../../features/trainer/components/ConfirmDialog';
import DataTable from '../../features/trainer/components/DataTable';
import FenBoard from '../../features/trainer/components/FenBoard';
import { toast } from '../../features/trainer/components/toastStore';
import {
  Button,
  ButtonLink,
  Empty,
  Loaded,
  Meter,
  PageHeader,
  Section,
  StatCard,
  Status,
} from '../../features/trainer/components/ui';

const ACTIONS = {
  publish: [
    'Publish',
    'Students will receive this assignment. It can no longer be edited afterwards.',
    'primary',
    'published',
  ],
  close: [
    'Close',
    'Closing marks the assignment completed. Students keep their recorded results.',
    'secondary',
    'closed',
  ],
  cancel: [
    'Cancel assignment',
    'Cancelled assignments are removed from students’ lists and excluded from completion rates.',
    'danger',
    'cancelled',
  ],
};

export default function AssignmentProgressPage() {
  const { params } = useRoute();
  const id = params.assignmentId;
  const detail = useLoader(() => trainerApi.assignment(id), [id]);
  const progress = useLoader(() => trainerApi.assignmentProgress(id), [id]);
  const [pending, setPending] = useState(null);
  const [busy, setBusy] = useState(false);

  async function runAction() {
    setBusy(true);
    try {
      await trainerApi.assignmentAction(id, pending);
      toast.success(`Assignment ${ACTIONS[pending][3]}.`);
      detail.reload();
      progress.reload();
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(false);
      setPending(null);
    }
  }

  return (
    <TrainerPage>
      <Loaded result={detail}>
        {(assignment) => {
          const available =
            {
              draft: ['publish', 'cancel'],
              published: ['close', 'cancel'],
            }[assignment.status] ?? [];

          return (
            <>
              <PageHeader
                back={{ to: '/trainer/assignments', label: 'Assignments' }}
                title={assignment.title}
                subtitle={
                  <>
                    {assignment.group && (
                      <Link to={`/trainer/groups/${assignment.group.id}`}>
                        {assignment.group.name}
                      </Link>
                    )}
                    {' · '}
                    {assignment.assignment_type === 'group' ? 'whole group' : 'selected students'}
                    {assignment.start_date && ` · starts ${formatDateTime(assignment.start_date)}`}
                    {assignment.due_date && ` · due ${formatDateTime(assignment.due_date)}`}
                  </>
                }
                actions={
                  <>
                    <Status value={assignment.status} />
                    {assignment.status === 'draft' && (
                      <ButtonLink
                        to={`/trainer/assignments/${assignment.id}/edit`}
                        variant="secondary"
                      >
                        Edit
                      </ButtonLink>
                    )}
                    {available.map((action) => (
                      <Button
                        key={action}
                        variant={ACTIONS[action][2] === 'danger' ? 'ghost' : ACTIONS[action][2]}
                        onClick={() => setPending(action)}
                      >
                        {ACTIONS[action][0]}
                      </Button>
                    ))}
                  </>
                }
              />
              {assignment.description && <p style={{ margin: 0 }}>{assignment.description}</p>}

              {assignment.status === 'draft' ? (
                <p className="tr-callout tr-callout--info">
                  This is a draft. Students see it only after you publish it.
                </p>
              ) : (
                <Loaded result={progress}>{(data) => <ProgressView data={data} />}</Loaded>
              )}

              <Section title={`Puzzles (${assignment.puzzles.length})`}>
                {assignment.puzzles.length ? (
                  <div className="tr-grid tr-grid--cards">
                    {assignment.puzzles.map((puzzle) => (
                      <Link
                        key={puzzle.puzzle_id}
                        to={`/trainer/puzzles/${puzzle.puzzle_id}`}
                        className="tr-puzzle-card"
                      >
                        <FenBoard
                          fen={puzzle.fen}
                          size="sm"
                          flipped={sideToMove(puzzle.fen) === 'Black'}
                        />
                        <span className="tr-puzzle-card__meta">
                          <strong>
                            #{puzzle.display_order} ·{' '}
                            {puzzle.rating ? `Rating ${puzzle.rating}` : 'Unrated'}
                          </strong>
                          <span className="tr-muted">
                            {titleCase(puzzle.difficulty) || '—'} · {sideToMove(puzzle.fen)} to move
                          </span>
                        </span>
                      </Link>
                    ))}
                  </div>
                ) : (
                  <Empty title="No puzzles yet" message="Edit the draft to add puzzles." />
                )}
              </Section>

              <ConfirmDialog
                open={Boolean(pending)}
                title={pending ? `${ACTIONS[pending][0]}?` : ''}
                message={pending ? ACTIONS[pending][1] : ''}
                confirmLabel={pending ? ACTIONS[pending][0] : ''}
                tone={pending ? ACTIONS[pending][2] : 'primary'}
                busy={busy}
                onConfirm={runAction}
                onCancel={() => setPending(null)}
              />
            </>
          );
        }}
      </Loaded>
    </TrainerPage>
  );
}

function ProgressView({ data }) {
  return (
    <>
      {data.is_overdue && (
        <p className="tr-callout tr-callout--error">
          The due date has passed and not every student has completed the assignment.
        </p>
      )}
      <div className="tr-grid tr-grid--stats">
        <StatCard
          label="Completion rate"
          value={formatPercent(data.completion_rate)}
          hint={`${data.completed_count} of ${data.recipients_total} students`}
        />
        <StatCard label="In progress" value={data.in_progress_count} />
        <StatCard label="Not started" value={data.not_started_count} />
        <StatCard
          label="Average progress"
          value={formatPercent(data.average_completion_percent)}
          hint={`${data.puzzles_total} puzzles each`}
        />
      </div>
      <Section title="Student progress">
        {data.recipients.length ? (
          <DataTable
            caption="Progress per student"
            rowKey="student_id"
            rows={data.recipients}
            onRowClick={(row) => navigate(`/trainer/students/${row.student_id}`)}
            columns={[
              {
                key: 'full_name',
                label: 'Student',
                render: (row) => <strong>{row.full_name}</strong>,
              },
              { key: 'status', label: 'Status', render: (row) => <Status value={row.status} /> },
              {
                key: 'solved',
                label: 'Solved',
                render: (row) => (
                  <span className="tr-row">
                    <Meter value={row.completion_percent} label={`${row.full_name} progress`} />
                    {row.puzzles_solved}/{row.puzzles_total}
                  </span>
                ),
              },
              { key: 'attempts', label: 'Attempts', align: 'right' },
              {
                key: 'submission',
                label: 'Submission',
                render: (row) =>
                  row.submission_status
                    ? `${titleCase(row.submission_status)}${row.submission_score !== null ? ` · ${row.submission_score}` : ''}`
                    : '—',
              },
              {
                key: 'last_activity_at',
                label: 'Last activity',
                render: (row) => (row.last_activity_at ? formatDate(row.last_activity_at) : '—'),
              },
              {
                key: 'review',
                label: 'Review',
                render: (row) => (
                  <Link
                    to={`/trainer/assignments/${data.assignment_id}/submissions/${row.student_id}`}
                    onClick={(event) => event.stopPropagation()}
                  >
                    {row.submission_status === 'submitted' ? 'Review submission' : 'View attempts'}
                  </Link>
                ),
              },
            ]}
          />
        ) : (
          <Empty title="No recipients" />
        )}
        <p className="tr-muted" style={{ marginBottom: 0, fontSize: '0.85rem' }}>
          A student completes the assignment once every puzzle has a solved attempt made within this
          assignment.
        </p>
      </Section>
    </>
  );
}
