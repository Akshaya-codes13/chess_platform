import { Link, navigate, useRoute } from '../../routes/router';
import { trainerApi } from '../../features/trainer/api';
import { formatTime, formatWeekday, localTimezone, titleCase } from '../../features/trainer/format';
import { useListState, useLoader } from '../../features/trainer/hooks';
import TrainerPage from '../../features/trainer/components/TrainerPage';
import Pagination from '../../features/trainer/components/Pagination';
import { FilterSelect } from '../../features/trainer/components/Field';
import {
  ButtonLink,
  Empty,
  Loaded,
  PageHeader,
  Section,
  Status,
} from '../../features/trainer/components/ui';

const SCOPES = [
  { id: 'active', label: 'Active' },
  { id: 'upcoming', label: 'Upcoming' },
  { id: 'completed', label: 'Completed' },
  { id: 'past', label: 'Past' },
  { id: 'all', label: 'All' },
];

export default function SessionsPage() {
  const { query: routeQuery } = useRoute();
  const scope = SCOPES.some((s) => s.id === routeQuery.scope) ? routeQuery.scope : 'upcoming';
  const [filters, setFilter] = useListState({ group_id: null, status: null });
  const query = { ...filters, scope };
  const groups = useLoader(() => trainerApi.groups({ page_size: 100 }), []);
  const result = useLoader(() => trainerApi.sessions(query), [JSON.stringify(query)]);

  return (
    <TrainerPage>
      <PageHeader
        title="Training sessions"
        subtitle={`Times are shown in your timezone (${localTimezone}).`}
        actions={<ButtonLink to="/trainer/sessions/new">Schedule session</ButtonLink>}
      />
      <div className="tr-tabs" role="tablist" aria-label="Session range">
        {SCOPES.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            className="tr-tab"
            aria-selected={scope === item.id}
            onClick={() => navigate(`/trainer/sessions?scope=${item.id}`)}
          >
            {item.label}
          </button>
        ))}
      </div>
      <Section>
        <div className="tr-filters">
          <FilterSelect
            label="Group"
            value={filters.group_id}
            onChange={(value) => setFilter('group_id', value)}
            options={
              groups.data?.items.map((group) => ({ value: group.id, label: group.name })) ?? []
            }
          />
          <FilterSelect
            label="Status"
            value={filters.status}
            onChange={(value) => setFilter('status', value)}
            options={['scheduled', 'ongoing', 'completed', 'cancelled'].map((value) => ({
              value,
              label: titleCase(value),
            }))}
          />
        </div>
        <Loaded result={result}>
          {(page) =>
            page.items.length ? (
              <>
                <Agenda sessions={page.items} />
                <Pagination
                  page={page.page}
                  pages={page.pages}
                  total={page.total}
                  label="sessions"
                  onChange={(value) => setFilter('page', value)}
                />
              </>
            ) : (
              <Empty
                title={scope === 'upcoming' ? 'No upcoming sessions' : 'No sessions found'}
                action={
                  scope === 'upcoming' && (
                    <ButtonLink to="/trainer/sessions/new" size="sm">
                      Schedule session
                    </ButtonLink>
                  )
                }
              />
            )
          }
        </Loaded>
      </Section>
    </TrainerPage>
  );
}

/** Sessions grouped by local calendar day. */
function Agenda({ sessions }) {
  const days = [];
  for (const session of sessions) {
    const key = new Date(session.start_time).toDateString();
    if (days.at(-1)?.key !== key) days.push({ key, sessions: [] });
    days.at(-1).sessions.push(session);
  }

  return days.map((day) => (
    <div key={day.key}>
      <h3 className="tr-agenda-day">{formatWeekday(day.sessions[0].start_time)}</h3>
      <ul className="tr-list">
        {day.sessions.map((session) => (
          <li key={session.id}>
            <span className="tr-row" style={{ flex: '1 1 260px' }}>
              <span className="tr-date-chip" style={{ minWidth: 72 }}>
                {formatTime(session.start_time)}
                <span style={{ fontWeight: 500 }}>{formatTime(session.end_time)}</span>
              </span>
              <span>
                <Link to={`/trainer/sessions/${session.id}`}>{session.title}</Link>
                <br />
                <span className="tr-muted">
                  {session.group?.name ?? 'No group'}
                  {session.learning_objective && ` · ${session.learning_objective}`}
                </span>
              </span>
            </span>
            <span className="tr-row">
              {session.status === 'completed' && (
                <span className="tr-muted">
                  {session.attendance_recorded}/{session.roster_size} attendance
                </span>
              )}
              <Status value={session.status} />
            </span>
          </li>
        ))}
      </ul>
    </div>
  ));
}
