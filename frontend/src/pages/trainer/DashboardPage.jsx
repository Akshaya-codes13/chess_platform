import { Link } from '../../routes/router';
import { trainerApi } from '../../features/trainer/api';
import {
  formatDate,
  formatDateTime,
  formatPercent,
  formatTimeRange,
  relativeDays,
} from '../../features/trainer/format';
import { useLoader } from '../../features/trainer/hooks';
import TrainerPage from '../../features/trainer/components/TrainerPage';
import {
  ButtonLink,
  Empty,
  Loaded,
  PageHeader,
  Section,
  StatCard,
  Status,
} from '../../features/trainer/components/ui';

export default function DashboardPage() {
  const result = useLoader(() => trainerApi.dashboard(), []);

  return (
    <TrainerPage>
      <Loaded result={result}>{(data) => <Dashboard data={data} />}</Loaded>
    </TrainerPage>
  );
}

function Dashboard({ data }) {
  const { profile, summary, performance } = data;
  const firstName = profile.full_name.split(' ')[0];

  return (
    <>
      <PageHeader
        title={`Welcome back, ${firstName}`}
        subtitle={profile.specialization || 'Trainer dashboard'}
        actions={
          <>
            <ButtonLink to="/trainer/assignments/new" variant="secondary">
              New assignment
            </ButtonLink>
            <ButtonLink to="/trainer/sessions/new">Schedule session</ButtonLink>
          </>
        }
      />

      <div className="tr-grid tr-grid--stats">
        <StatCard label="Assigned groups" value={summary.group_count} to="/trainer/groups" />
        <StatCard label="Students" value={summary.student_count} hint="across your groups" />
        <StatCard
          label="Active assignments"
          value={summary.active_assignments}
          to="/trainer/assignments"
        />
        <StatCard
          label="Upcoming sessions"
          value={summary.upcoming_sessions}
          to="/trainer/sessions"
        />
        <StatCard label="Puzzles created" value={summary.puzzles_created} to="/trainer/puzzles" />
        <StatCard label="Sessions completed" value={summary.completed_sessions} />
      </div>

      <Section title={`Student performance · last ${performance.window_days} days`}>
        <div className="tr-grid tr-grid--stats">
          <StatCard
            label="Puzzle accuracy"
            value={formatPercent(performance.accuracy_percent)}
            hint={`${performance.solved} solved of ${performance.attempts} attempts`}
          />
          <StatCard
            label="Active students"
            value={performance.active_students}
            hint="attempted a puzzle"
          />
          <StatCard
            label="Assignment completion"
            value={formatPercent(performance.assignment_completion_rate)}
            hint="all published assignments"
          />
          <StatCard
            label="Attendance rate"
            value={formatPercent(performance.attendance_rate)}
            hint="present or late"
          />
        </div>
      </Section>

      <div className="tr-grid tr-grid--2">
        <Section title="Upcoming schedule" actions={<Link to="/trainer/sessions">View all</Link>}>
          {data.upcoming_sessions.length ? (
            <ul className="tr-list">
              {data.upcoming_sessions.map((session) => (
                <li key={session.id}>
                  <span className="tr-row">
                    <DateChip value={session.start_time} />
                    <span>
                      <Link to={`/trainer/sessions/${session.id}`}>{session.title}</Link>
                      <br />
                      <span className="tr-muted">
                        {session.group?.name} ·{' '}
                        {formatTimeRange(session.start_time, session.end_time)}
                      </span>
                    </span>
                  </span>
                  <span className="tr-muted">{relativeDays(session.start_time)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <Empty
              title="Nothing scheduled"
              message="Schedule a session for one of your groups."
              action={
                <ButtonLink to="/trainer/sessions/new" size="sm">
                  Schedule session
                </ButtonLink>
              }
            />
          )}
        </Section>

        <Section
          title="Recent assignments"
          actions={<Link to="/trainer/assignments">View all</Link>}
        >
          {data.recent_assignments.length ? (
            <ul className="tr-list">
              {data.recent_assignments.map((assignment) => (
                <li key={assignment.id}>
                  <span>
                    <Link to={`/trainer/assignments/${assignment.id}`}>{assignment.title}</Link>
                    <br />
                    <span className="tr-muted">
                      {assignment.group?.name} · {assignment.completed_count}/
                      {assignment.recipient_count} completed
                      {assignment.due_date && ` · due ${formatDate(assignment.due_date)}`}
                    </span>
                  </span>
                  <Status value={assignment.status} />
                </li>
              ))}
            </ul>
          ) : (
            <Empty
              title="No assignments yet"
              action={
                <ButtonLink to="/trainer/assignments/new" size="sm">
                  Create assignment
                </ButtonLink>
              }
            />
          )}
        </Section>

        <Section title="Your groups" actions={<Link to="/trainer/groups">View all</Link>}>
          {data.groups.length ? (
            <ul className="tr-list">
              {data.groups.map((group) => (
                <li key={group.id}>
                  <Link to={`/trainer/groups/${group.id}`}>{group.name}</Link>
                  <span className="tr-row">
                    <span className="tr-muted">{group.student_count} students</span>
                    {!group.is_active && <Status value="inactive" />}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <Empty
              title="No groups assigned"
              message="An administrator assigns groups to trainers."
            />
          )}
        </Section>

        <Section title="Recent student activity">
          {data.recent_activity.length ? (
            <ul className="tr-list">
              {data.recent_activity.map((item, index) => (
                <li key={`${item.student_id}-${item.occurred_at}-${index}`}>
                  <span>
                    <Link to={`/trainer/students/${item.student_id}`}>
                      {item.student_name || 'Student'}
                    </Link>{' '}
                    <span className="tr-muted">{item.description.toLowerCase()}</span>
                  </span>
                  <span className="tr-muted">{formatDateTime(item.occurred_at)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <Empty
              title="No recent activity"
              message="Puzzle attempts by your students appear here."
            />
          )}
        </Section>

        <Section title="Recently completed sessions">
          {data.recent_completed_sessions.length ? (
            <ul className="tr-list">
              {data.recent_completed_sessions.map((session) => (
                <li key={session.id}>
                  <span>
                    <Link to={`/trainer/sessions/${session.id}`}>{session.title}</Link>
                    <br />
                    <span className="tr-muted">
                      {session.group?.name} · {formatDate(session.start_time)}
                    </span>
                  </span>
                  <span className="tr-muted">
                    {session.attendance_recorded}/{session.roster_size} recorded
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <Empty title="No completed sessions yet" />
          )}
        </Section>
      </div>
    </>
  );
}

function DateChip({ value }) {
  const date = new Date(value);
  return (
    <span className="tr-date-chip" aria-hidden="true">
      {date.toLocaleDateString(undefined, { month: 'short' })}
      <strong>{date.getDate()}</strong>
    </span>
  );
}
