import { Link, useRoute } from '../../routes/router';
import { trainerApi } from '../../features/trainer/api';
import {
  formatDate,
  formatDateTime,
  formatPercent,
  titleCase,
} from '../../features/trainer/format';
import { useLoader } from '../../features/trainer/hooks';
import TrainerPage from '../../features/trainer/components/TrainerPage';
import {
  Empty,
  Loaded,
  Meter,
  PageHeader,
  Section,
  StatCard,
  Status,
} from '../../features/trainer/components/ui';

export default function StudentPerformancePage() {
  const { params } = useRoute();
  const result = useLoader(
    () => trainerApi.studentPerformance(params.studentId),
    [params.studentId],
  );

  return (
    <TrainerPage>
      <Loaded result={result}>{(data) => <Performance data={data} />}</Loaded>
    </TrainerPage>
  );
}

function Performance({ data }) {
  const { student, metrics } = data;
  const firstGroup = data.groups[0];

  return (
    <>
      <PageHeader
        back={
          firstGroup
            ? { to: `/trainer/groups/${firstGroup.id}`, label: firstGroup.name }
            : { to: '/trainer/groups', label: 'My groups' }
        }
        title={student.full_name}
        subtitle={`${student.email} · rating ${student.chess_rating} · ${titleCase(student.level)}`}
        actions={!student.is_active && <Status value="inactive" />}
      />

      <div className="tr-grid tr-grid--stats">
        <StatCard
          label="Puzzles attempted"
          value={metrics.puzzles_attempted}
          hint={`${metrics.total_attempts} attempts in total`}
        />
        <StatCard label="Puzzles solved" value={metrics.puzzles_solved} />
        <StatCard
          label="Accuracy"
          value={formatPercent(metrics.accuracy_percent)}
          hint="solved attempts ÷ all attempts"
        />
        <StatCard
          label="Assignment completion"
          value={formatPercent(metrics.assignment_completion_rate)}
          hint={`${metrics.assignments_completed} of ${metrics.assignments_received} assignments`}
        />
        <StatCard
          label="Attendance"
          value={formatPercent(metrics.attendance_rate)}
          hint={`${metrics.sessions_attended} of ${metrics.sessions_recorded} sessions`}
        />
        <StatCard
          label="XP"
          value={metrics.total_xp}
          hint={`streak ${metrics.current_streak} · best ${metrics.longest_streak}`}
        />
      </div>

      <div className="tr-grid tr-grid--2">
        <Section title="Progress over time" actions={<Legend />}>
          <ProgressChart points={data.progress} />
        </Section>

        <Section title="Assignments">
          {data.assignments.length ? (
            <ul className="tr-list">
              {data.assignments.map((item) => (
                <li key={item.assignment_id}>
                  <span style={{ flex: '1 1 180px' }}>
                    <Link to={`/trainer/assignments/${item.assignment_id}`}>{item.title}</Link>
                    <br />
                    <span className="tr-muted">
                      {item.puzzles_solved}/{item.puzzles_total} solved
                      {item.due_date && ` · due ${formatDate(item.due_date)}`}
                    </span>
                  </span>
                  <span className="tr-row">
                    <Meter
                      value={
                        item.puzzles_total ? (item.puzzles_solved / item.puzzles_total) * 100 : 0
                      }
                      label={`${item.title} progress`}
                    />
                    <Status value={item.completed ? 'completed' : 'in_progress'} />
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <Empty
              title="No assignments yet"
              message="Published assignments you give this student appear here."
            />
          )}
        </Section>

        <Section title="Recent activity">
          {data.recent_activity.length ? (
            <ul className="tr-list">
              {data.recent_activity.map((item, index) => (
                <li key={`${item.kind}-${item.occurred_at}-${index}`}>
                  <span>{item.description}</span>
                  <span className="tr-muted">{formatDateTime(item.occurred_at)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <Empty title="No activity yet" />
          )}
        </Section>

        <Section title={`Badges (${data.badges.length})`}>
          {data.badges.length ? (
            <ul className="tr-list">
              {data.badges.map((badge) => (
                <li key={badge.code}>
                  <span>
                    <strong>🏅 {badge.name}</strong>
                    {badge.description && (
                      <>
                        <br />
                        <span className="tr-muted">{badge.description}</span>
                      </>
                    )}
                  </span>
                  <span className="tr-muted">{formatDate(badge.earned_at)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <Empty title="No badges earned yet" />
          )}
          <p className="tr-muted" style={{ marginBottom: 0 }}>
            Groups: {data.groups.map((group) => group.name).join(', ')}
          </p>
        </Section>
      </div>
    </>
  );
}

function Legend() {
  return (
    <span className="tr-legend">
      <span>
        <i style={{ background: 'var(--tr-accent)' }} />
        Solved
      </span>
      <span>
        <i style={{ background: 'var(--tr-brass)', opacity: 0.55 }} />
        Not solved
      </span>
    </span>
  );
}

function ProgressChart({ points }) {
  const max = Math.max(1, ...points.map((point) => point.attempts));
  const total = points.reduce((sum, point) => sum + point.attempts, 0);

  if (!total) return <Empty title="No puzzle attempts in the last 12 weeks" />;

  return (
    <>
      <div
        className="tr-bars"
        role="img"
        aria-label="Weekly puzzle attempts and solves for the last 12 weeks"
      >
        {points.map((point) => (
          <div
            key={point.week_start}
            className="tr-bars__col"
            title={`Week of ${formatDate(point.week_start)}: ${point.solved}/${point.attempts} solved (${formatPercent(point.accuracy_percent)})`}
          >
            <div className="tr-bars__stack" style={{ height: `${(point.attempts / max) * 100}%` }}>
              <div className="tr-bars__solved" style={{ flex: point.solved }} />
              <div className="tr-bars__missed" style={{ flex: point.attempts - point.solved }} />
            </div>
            <span className="tr-bars__label">
              {new Date(`${point.week_start}T00:00:00`).toLocaleDateString(undefined, {
                month: 'numeric',
                day: 'numeric',
              })}
            </span>
          </div>
        ))}
      </div>
      <table className="tr-visually-hidden">
        <caption>Weekly attempts</caption>
        <tbody>
          {points.map((point) => (
            <tr key={point.week_start}>
              <th scope="row">{point.week_start}</th>
              <td>
                {point.attempts} attempts, {point.solved} solved
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
