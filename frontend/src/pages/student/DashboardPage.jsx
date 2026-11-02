import Button from '../../components/ui/Button';
import Card from '../../components/ui/Card';
import EmptyState from '../../components/ui/EmptyState';
import LoadState from '../../components/ui/LoadState';
import ProgressBar from '../../components/ui/ProgressBar';
import { useApi } from '../../hooks/useApi';
import { dueLabel, formatPercent, titleCase } from '../../lib/format';
import { Link } from '../../routes/router';
import {
  AssignmentRow,
  AttemptRow,
  BadgeTile,
  MilestoneMeter,
  SessionRow,
  StatStrip,
  TrainerCard,
} from './components';

export default function DashboardPage() {
  const { data, error, loading, reload } = useApi('/student/dashboard');

  if (loading || error) return <LoadState loading={loading} error={error} onRetry={reload} />;

  const { profile, stats, assignment_counts: counts } = data;
  const next = data.active_assignments[0];
  const firstName = profile.full_name.split(' ')[0];

  return (
    <div className="page dashboard">
      <header className="page-header">
        <div>
          <h1>Welcome back, {firstName}</h1>
          <p className="page-subtitle">
            {titleCase(profile.level)} · rating {profile.chess_rating}
          </p>
        </div>
      </header>

      {next ? (
        <section className="next-up" aria-labelledby="next-up-title">
          <div className="next-up-text">
            <p className="next-up-kicker">
              {next.status === 'overdue' ? 'Overdue — finish this first' : 'Your next assignment'}
            </p>
            <h2 id="next-up-title">{next.title}</h2>
            <p className="row-meta">
              {dueLabel(next.due_date, next.status)} · {next.progress.remaining_puzzles} puzzle
              {next.progress.remaining_puzzles === 1 ? '' : 's'} left
            </p>
            <ProgressBar
              value={next.progress.completion_percent}
              label={`${next.progress.completed_puzzles} of ${next.progress.total_puzzles} solved`}
            />
          </div>
          <Button to={`/student/assignments/${next.id}`}>
            {next.progress.attempts ? 'Continue' : 'Start'}
          </Button>
        </section>
      ) : (
        <section className="next-up is-clear">
          <div className="next-up-text">
            <h2>You are all caught up</h2>
            <p className="row-meta">New assignments from your trainer will appear here.</p>
          </div>
        </section>
      )}

      <StatStrip
        items={[
          { label: 'Puzzles solved', value: stats.puzzles_solved },
          {
            label: 'Accuracy',
            value: formatPercent(stats.accuracy_percent),
            hint: `${stats.total_attempts} attempts`,
          },
          { label: 'XP', value: stats.total_xp, tone: 'reward' },
          {
            label: 'Streak',
            value: `${stats.current_streak} day${stats.current_streak === 1 ? '' : 's'}`,
            hint: `Best ${stats.longest_streak}`,
            tone: 'reward',
          },
          { label: 'Badges', value: stats.badges_earned },
        ]}
      />

      <div className="dashboard-grid">
        <Card
          title="Assignments"
          actions={<Link to="/student/assignments">All assignments</Link>}
          className="span-2"
        >
          <p className="count-line">
            {counts.pending} not started · {counts.in_progress} in progress · {counts.overdue}{' '}
            overdue · {counts.completed} completed
          </p>
          {data.active_assignments.length ? (
            <ul className="row-list">
              {data.active_assignments.map((a) => (
                <AssignmentRow key={a.id} assignment={a} />
              ))}
            </ul>
          ) : (
            <EmptyState
              title="No open assignments"
              message="Completed work stays under All assignments."
            />
          )}
          {data.recently_completed.length > 0 && (
            <>
              <h3 className="subheading">Recently completed</h3>
              <ul className="row-list">
                {data.recently_completed.map((a) => (
                  <AssignmentRow key={a.id} assignment={a} />
                ))}
              </ul>
            </>
          )}
        </Card>

        <Card title="Upcoming classes" actions={<Link to="/student/sessions">Schedule</Link>}>
          {data.upcoming_sessions.length ? (
            <ul className="row-list">
              {data.upcoming_sessions.map((s) => (
                <SessionRow key={s.id} session={s} />
              ))}
            </ul>
          ) : (
            <EmptyState
              title="No classes scheduled"
              message="Your trainer has not scheduled the next class yet."
            />
          )}
        </Card>

        <Card title="Recent puzzles" actions={<Link to="/student/progress">Progress</Link>}>
          {data.recent_attempts.length ? (
            <ul className="row-list">
              {data.recent_attempts.map((a) => (
                <AttemptRow key={a.id} attempt={a} />
              ))}
            </ul>
          ) : (
            <EmptyState
              title="No puzzles tried yet"
              message="Open an assignment to solve your first puzzle."
            />
          )}
        </Card>

        <Card title="Your trainer">
          {data.trainer ? (
            <TrainerCard trainer={data.trainer} />
          ) : (
            <p className="row-meta">No trainer assigned.</p>
          )}
          {data.groups.length > 0 && (
            <p className="row-meta group-line">
              Groups:{' '}
              {data.groups.map((g, i) => (
                <span key={g.id}>
                  {i > 0 && ', '}
                  <Link to={`/student/groups/${g.id}`}>{g.name}</Link>
                </span>
              ))}
            </p>
          )}
        </Card>

        <Card title="Achievements" actions={<Link to="/student/achievements">XP and badges</Link>}>
          <MilestoneMeter milestone={data.next_milestone} />
          {data.recent_badges.length > 0 && (
            <ul className="badge-grid is-compact">
              {data.recent_badges.map((b) => (
                <BadgeTile key={b.id} badge={b} />
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
