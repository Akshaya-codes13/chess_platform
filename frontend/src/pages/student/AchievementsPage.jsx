import ConsistencyCalendar from '../../components/charts/ConsistencyCalendar';
import Button from '../../components/ui/Button';
import ProgressBar from '../../components/ui/ProgressBar';
import Card from '../../components/ui/Card';
import EmptyState from '../../components/ui/EmptyState';
import LoadState from '../../components/ui/LoadState';
import PageHeader from '../../components/ui/PageHeader';
import { useApi } from '../../hooks/useApi';
import { formatDate, formatDateTime, titleCase } from '../../lib/format';
import { BadgeTile, MilestoneMeter } from './components';

export default function AchievementsPage() {
  const { data, error, loading, reload } = useApi('/student/gamification');

  if (loading || error) return <LoadState loading={loading} error={error} onRetry={reload} />;

  return (
    <div className="page">
      <PageHeader
        title="XP and achievements"
        subtitle={data.level ? `${titleCase(data.level)} level` : undefined}
        actions={
          <Button variant="secondary" to="/student/badges">
            Badge collection
          </Button>
        }
      />

      <section className="xp-hero" aria-label="XP summary">
        <div className="xp-level">
          <p className="xp-total">
            {data.total_xp}
            <span> XP</span>
          </p>
          <p className="xp-level__name">Level {data.xp_level.level}</p>
          <ProgressBar
            value={data.xp_level.progress_percent}
            label={`${data.xp_level.xp_to_next_level} XP to level ${data.xp_level.level + 1}`}
          />
        </div>
        <dl className="xp-facts">
          <div>
            <dt>Current streak</dt>
            <dd>
              {data.current_streak} day{data.current_streak === 1 ? '' : 's'}
            </dd>
          </div>
          <div>
            <dt>Longest streak</dt>
            <dd>
              {data.longest_streak} day{data.longest_streak === 1 ? '' : 's'}
            </dd>
          </div>
          <div>
            <dt>Last active</dt>
            <dd>{data.last_activity_date ? formatDate(data.last_activity_date) : 'Not yet'}</dd>
          </div>
          <div>
            <dt>Badges</dt>
            <dd>
              {data.badges_earned} of {data.badges_total}
            </dd>
          </div>
          <div>
            <dt>Assignments completed</dt>
            <dd>{data.assignments_completed}</dd>
          </div>
        </dl>
      </section>

      <Card
        title={`Consistency · ${data.active_days} active days in the last ${data.activity_calendar.length}`}
      >
        <ConsistencyCalendar days={data.activity_calendar} title="Puzzles attempted per day" />
      </Card>

      <div className="two-column">
        <Card title="Next milestone">
          <MilestoneMeter milestone={data.next_milestone} />
        </Card>
        <Card title="Recent badges">
          {data.recent_badges.length ? (
            <ul className="badge-grid is-compact">
              {data.recent_badges.map((b) => (
                <BadgeTile key={b.id} badge={b} />
              ))}
            </ul>
          ) : (
            <EmptyState title="No badges yet" message="Solve your first puzzle to earn one." />
          )}
        </Card>
      </div>

      <Card title="Recent XP">
        {data.recent_xp.length ? (
          <ul className="xp-log">
            {data.recent_xp.map((event) => (
              <li key={event.id}>
                <span className="xp-points">+{event.points}</span>
                <span>{event.reason}</span>
                <time className="row-meta" dateTime={event.created_at}>
                  {formatDateTime(event.created_at)}
                </time>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState
            title="No XP yet"
            message="XP is earned the first time you solve each puzzle."
          />
        )}
      </Card>

      <p className="hint">
        XP and badges are awarded by the academy server when a solve is verified. Each puzzle earns
        XP once, completing an assignment earns a bonus once, and each badge is awarded once.
      </p>
    </div>
  );
}
