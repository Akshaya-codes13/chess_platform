import { Link, navigate, useRoute } from '../../routes/router';
import { adminApi } from '../../features/admin/api';
import ActivityList from '../../features/admin/components/ActivityList';
import AdminPage from '../../features/admin/components/AdminPage';
import { Breakdown, UserLink } from '../../features/admin/components/shared';
import DataTable from '../../features/trainer/components/DataTable';
import { FilterSelect, SearchInput } from '../../features/trainer/components/Field';
import Pagination from '../../features/trainer/components/Pagination';
import {
  Empty,
  Loaded,
  PageHeader,
  Section,
  StatCard,
  Status,
} from '../../features/trainer/components/ui';
import {
  formatDate,
  formatPercent,
  formatTimeRange,
  titleCase,
} from '../../features/trainer/format';
import { useDebounced, useListState, useLoader } from '../../features/trainer/hooks';

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'assignments', label: 'Assignments' },
  { id: 'sessions', label: 'Sessions' },
  { id: 'activity', label: 'Activity log' },
];

const toOptions = (values) => values.map((value) => ({ value, label: titleCase(value) }));

function GroupLink({ group }) {
  if (!group) return <span className="tr-muted">Individual</span>;
  return <Link to={`/admin/groups/${group.id}`}>{group.name}</Link>;
}

function Overview() {
  const result = useLoader(() => adminApi.reports(), []);
  return (
    <Loaded result={result}>
      {(report) => (
        <>
          <div className="tr-grid tr-grid--stats">
            <StatCard
              label="Attendance rate"
              value={formatPercent(report.attendance_rate)}
              hint="Present or late, of marked records"
            />
            <StatCard
              label="Puzzle attempts"
              value={report.puzzle_attempts.total}
              hint={`${report.puzzle_attempts.solve_rate}% solved`}
            />
            <StatCard label="Games" value={report.games.total} />
            <StatCard
              label="XP earned"
              value={report.gamification.total_xp}
              hint={`${report.gamification.average_xp} average per student`}
            />
            <StatCard
              label="Badges awarded"
              value={report.gamification.badges_awarded}
              hint={`${report.gamification.badges_defined} badges defined`}
            />
          </div>
          <div className="tr-grid tr-grid--2">
            <Section title="Assignments by status">
              <Breakdown counts={report.assignments_by_status} label="Assignments by status" />
            </Section>
            <Section title="Submissions by status">
              <Breakdown counts={report.submissions_by_status} label="Submissions by status" />
            </Section>
            <Section title="Sessions by status">
              <Breakdown counts={report.sessions_by_status} label="Sessions by status" />
            </Section>
            <Section title="Attendance">
              <Breakdown counts={report.attendance_by_status} label="Attendance by status" />
            </Section>
            <Section title="Games by status">
              <Breakdown counts={report.games.by_status} label="Games by status" />
            </Section>
            <Section title="Game results">
              <Breakdown counts={report.games.by_result} label="Game results" />
            </Section>
          </div>
          <Section title="Top students by XP">
            {report.gamification.top_students.length ? (
              <DataTable
                caption="Top students by XP"
                rows={report.gamification.top_students}
                columns={[
                  {
                    key: 'full_name',
                    label: 'Student',
                    render: (s) => <UserLink user={s} role="student" />,
                  },
                  { key: 'total_xp', label: 'XP', align: 'right' },
                  { key: 'current_streak', label: 'Streak', align: 'right' },
                  { key: 'puzzles_solved', label: 'Puzzles solved', align: 'right' },
                ]}
              />
            ) : (
              <Empty title="No progress recorded yet" />
            )}
          </Section>
        </>
      )}
    </Loaded>
  );
}

function Assignments() {
  const [filters, setFilter] = useListState({ search: '', status: null });
  const search = useDebounced(filters.search);
  const query = { ...filters, search };
  const result = useLoader(() => adminApi.assignments(query), [JSON.stringify(query)]);

  return (
    <Section>
      <div className="tr-filters">
        <SearchInput
          label="Search by title"
          value={filters.search}
          onChange={(value) => setFilter('search', value)}
        />
        <FilterSelect
          label="Status"
          value={filters.status}
          onChange={(value) => setFilter('status', value)}
          options={toOptions(['draft', 'published', 'completed', 'cancelled'])}
        />
      </div>
      <Loaded result={result}>
        {(page) =>
          page.items.length ? (
            <>
              <DataTable
                caption="Assignments"
                rows={page.items}
                columns={[
                  { key: 'title', label: 'Assignment' },
                  { key: 'status', label: 'Status', render: (a) => <Status value={a.status} /> },
                  {
                    key: 'trainer',
                    label: 'Trainer',
                    render: (a) => <UserLink user={a.trainer} role="trainer" />,
                  },
                  { key: 'group', label: 'Group', render: (a) => <GroupLink group={a.group} /> },
                  { key: 'puzzle_count', label: 'Puzzles', align: 'right' },
                  { key: 'recipient_count', label: 'Students', align: 'right' },
                  { key: 'submission_count', label: 'Submissions', align: 'right' },
                  { key: 'due_date', label: 'Due', render: (a) => formatDate(a.due_date) },
                ]}
              />
              <Pagination
                page={page.page}
                pages={page.pages}
                total={page.total}
                label="assignments"
                onChange={(value) => setFilter('page', value)}
              />
            </>
          ) : (
            <Empty
              title="No assignments found"
              message="Trainers create assignments for their groups."
            />
          )
        }
      </Loaded>
    </Section>
  );
}

function Sessions({ groupId }) {
  const [filters, setFilter] = useListState({
    timeframe: 'upcoming',
    status: null,
    group_id: groupId ?? null,
  });
  const result = useLoader(() => adminApi.sessions(filters), [JSON.stringify(filters)]);

  return (
    <Section>
      <div className="tr-filters">
        <FilterSelect
          label="When"
          value={filters.timeframe}
          onChange={(value) => setFilter('timeframe', value)}
          allLabel="Any time"
          options={[
            { value: 'upcoming', label: 'Upcoming' },
            { value: 'past', label: 'Past' },
          ]}
        />
        <FilterSelect
          label="Status"
          value={filters.status}
          onChange={(value) => setFilter('status', value)}
          options={toOptions(['scheduled', 'ongoing', 'completed', 'cancelled'])}
        />
        {filters.group_id && (
          <button
            type="button"
            className="tr-btn tr-btn--ghost tr-btn--sm"
            onClick={() => setFilter('group_id', null)}
          >
            Show all groups
          </button>
        )}
      </div>
      <Loaded result={result}>
        {(page) =>
          page.items.length ? (
            <>
              <DataTable
                caption="Training sessions"
                rows={page.items}
                columns={[
                  { key: 'title', label: 'Session' },
                  {
                    key: 'time',
                    label: 'When',
                    render: (s) => formatTimeRange(s.start_time, s.end_time),
                  },
                  { key: 'status', label: 'Status', render: (s) => <Status value={s.status} /> },
                  {
                    key: 'trainer',
                    label: 'Trainer',
                    render: (s) => <UserLink user={s.trainer} role="trainer" />,
                  },
                  { key: 'group', label: 'Group', render: (s) => <GroupLink group={s.group} /> },
                  {
                    key: 'attendance',
                    label: 'Attendance',
                    render: (s) =>
                      Object.keys(s.attendance).length ? (
                        Object.entries(s.attendance)
                          .map(([status, count]) => `${count} ${status}`)
                          .join(', ')
                      ) : (
                        <span className="tr-muted">Not marked</span>
                      ),
                  },
                ]}
              />
              <Pagination
                page={page.page}
                pages={page.pages}
                total={page.total}
                label="sessions"
                onChange={(value) => setFilter('page', value)}
              />
            </>
          ) : (
            <Empty title="No sessions found" message="Try a different time range or status." />
          )
        }
      </Loaded>
    </Section>
  );
}

function Activity() {
  const [filters, setFilter] = useListState({ entity_type: null });
  const result = useLoader(() => adminApi.activity(filters), [JSON.stringify(filters)]);

  return (
    <Section>
      <div className="tr-filters">
        <FilterSelect
          label="Record type"
          value={filters.entity_type}
          onChange={(value) => setFilter('entity_type', value)}
          options={toOptions(['user', 'group', 'puzzle'])}
        />
      </div>
      <Loaded result={result}>
        {(page) => (
          <>
            <ActivityList items={page.items} empty="Admin actions are recorded here." />
            <Pagination
              page={page.page}
              pages={page.pages}
              total={page.total}
              label="entries"
              onChange={(value) => setFilter('page', value)}
            />
          </>
        )}
      </Loaded>
    </Section>
  );
}

export default function ReportsPage() {
  const { query } = useRoute();
  const tab = TABS.some((t) => t.id === query.tab) ? query.tab : 'overview';

  return (
    <AdminPage>
      <PageHeader title="Reports" subtitle="Platform-wide figures computed from stored records." />
      <div className="tr-tabs" role="tablist" aria-label="Report sections">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            className="tr-tab"
            aria-selected={tab === item.id}
            onClick={() => navigate(`/admin/reports?tab=${item.id}`, { replace: true })}
          >
            {item.label}
          </button>
        ))}
      </div>
      {tab === 'overview' && <Overview />}
      {tab === 'assignments' && <Assignments />}
      {tab === 'sessions' && <Sessions groupId={query.group_id} />}
      {tab === 'activity' && <Activity />}
    </AdminPage>
  );
}
