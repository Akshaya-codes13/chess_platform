import Button from '../../components/ui/Button';
import Card from '../../components/ui/Card';
import EmptyState from '../../components/ui/EmptyState';
import LoadState from '../../components/ui/LoadState';
import PageHeader from '../../components/ui/PageHeader';
import ProgressBar from '../../components/ui/ProgressBar';
import StatusBadge from '../../components/ui/StatusBadge';
import { useApi } from '../../hooks/useApi';
import {
  dueLabel,
  formatDate,
  formatDateTime,
  formatSeconds,
  statusLabel,
  titleCase,
} from '../../lib/format';
import { Link, useRoute } from '../../routes/router';
import { StatStrip } from './components';

export default function AssignmentDetailPage() {
  const { params } = useRoute();
  const { data, error, loading, reload } = useApi(`/student/assignments/${params.assignmentId}`);

  if (loading || error) return <LoadState loading={loading} error={error} onRetry={reload} />;

  const { progress, submission } = data;
  const resume = data.puzzles.find((p) => p.status !== 'solved') ?? data.puzzles[0];
  const puzzlePath = (id) => `/student/assignments/${data.id}/puzzles/${id}`;

  return (
    <div className="page">
      <PageHeader
        back={{ to: '/student/assignments', label: 'Assignments' }}
        title={data.title}
        subtitle={`${data.group_name ?? 'Individual assignment'} · set by ${data.trainer_name}`}
        actions={
          resume &&
          !data.is_closed && (
            <Button to={puzzlePath(resume.puzzle_id)}>
              {data.status === 'completed'
                ? 'Practise again'
                : progress.attempts
                  ? 'Resume'
                  : 'Start'}
            </Button>
          )
        }
      />

      <div className="detail-status">
        <StatusBadge status={data.status} />
        <span className={data.status === 'overdue' ? 'is-warning' : ''}>
          {dueLabel(data.due_date, data.status)}
        </span>
        {data.due_date && <span className="row-meta">Due {formatDateTime(data.due_date)}</span>}
        {data.is_closed && (
          <span className="row-meta">Closed by your trainer — new attempts are not accepted.</span>
        )}
      </div>

      {data.description && (
        <Card title="Instructions">
          <p className="prose">{data.description}</p>
        </Card>
      )}

      <Card title="Progress">
        <ProgressBar
          value={progress.completion_percent}
          label={`${progress.completed_puzzles} of ${progress.total_puzzles} puzzles solved (${progress.completion_percent}%)`}
          tone={data.status === 'completed' ? 'success' : 'default'}
        />
        <StatStrip
          items={[
            { label: 'Solved', value: progress.completed_puzzles },
            { label: 'Remaining', value: progress.remaining_puzzles },
            { label: 'Points', value: `${progress.earned_points} / ${progress.total_points}` },
            { label: 'Attempts', value: progress.attempts },
          ]}
        />
        <p className="row-meta">
          {submission
            ? `Submitted automatically on ${formatDate(submission.submitted_at)} with ${submission.score} points · ${statusLabel(submission.status)}`
            : 'Submitted automatically once every puzzle is solved.'}
        </p>
        {submission?.trainer_feedback && (
          <blockquote className="feedback">
            <p>{submission.trainer_feedback}</p>
            <footer>Feedback from {data.trainer_name}</footer>
          </blockquote>
        )}
      </Card>

      <Card title="Puzzles">
        {data.puzzles.length ? (
          <ol className="puzzle-list">
            {data.puzzles.map((p, index) => (
              <li key={p.puzzle_id}>
                <Link to={puzzlePath(p.puzzle_id)} className={`puzzle-item is-${p.status}`}>
                  <span className="puzzle-index">{index + 1}</span>
                  <span className="row-main">
                    <span className="row-title">
                      {p.themes.length ? p.themes.join(', ') : 'Tactics puzzle'}
                    </span>
                    <span className="row-meta">
                      {[
                        p.rating && `Rating ${p.rating}`,
                        p.difficulty && titleCase(p.difficulty),
                        `${p.points} pt`,
                      ]
                        .filter(Boolean)
                        .join(' · ')}
                    </span>
                  </span>
                  <span className="row-side">
                    <StatusBadge status={p.status} />
                    <span className="row-meta">
                      {p.status === 'solved'
                        ? `Best ${formatSeconds(p.best_time_seconds)}`
                        : p.attempts
                          ? `${p.attempts} attempt${p.attempts === 1 ? '' : 's'}`
                          : ''}
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ol>
        ) : (
          <EmptyState
            title="No puzzles yet"
            message="Your trainer has not added puzzles to this assignment."
          />
        )}
      </Card>
    </div>
  );
}
