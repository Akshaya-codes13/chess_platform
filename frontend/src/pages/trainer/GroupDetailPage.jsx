import { navigate, useRoute } from '../../routes/router';
import { trainerApi } from '../../features/trainer/api';
import {
  formatDate,
  formatDateTime,
  formatPercent,
  titleCase,
} from '../../features/trainer/format';
import { useDebounced, useListState, useLoader } from '../../features/trainer/hooks';
import TrainerPage from '../../features/trainer/components/TrainerPage';
import DataTable from '../../features/trainer/components/DataTable';
import Pagination from '../../features/trainer/components/Pagination';
import { SearchInput } from '../../features/trainer/components/Field';
import {
  ButtonLink,
  Empty,
  Loaded,
  Meter,
  PageHeader,
  Section,
  StatCard,
  Status,
} from '../../features/trainer/components/ui';

const TABS = [
  { id: 'students', label: 'Students' },
  { id: 'performance', label: 'Performance' },
  { id: 'assignments', label: 'Assignment history' },
];

export default function GroupDetailPage() {
  const { params, query } = useRoute();
  const tab = TABS.some((t) => t.id === query.tab) ? query.tab : 'students';
  const result = useLoader(() => trainerApi.group(params.groupId), [params.groupId]);

  return (
    <TrainerPage>
      <Loaded result={result}>
        {(group) => (
          <>
            <PageHeader
              back={{ to: '/trainer/groups', label: 'My groups' }}
              title={group.name}
              subtitle={group.description}
              actions={
                group.is_active ? (
                  <>
                    <ButtonLink
                      to={`/trainer/assignments/new?group=${group.id}`}
                      variant="secondary"
                    >
                      New assignment
                    </ButtonLink>
                    <ButtonLink to={`/trainer/sessions/new?group=${group.id}`}>
                      Schedule session
                    </ButtonLink>
                  </>
                ) : (
                  <Status value="inactive" />
                )
              }
            />
            <div className="tr-grid tr-grid--stats">
              <StatCard label="Students" value={group.student_count} />
              <StatCard label="Active assignments" value={group.active_assignment_count} />
              <StatCard
                label="Upcoming sessions"
                value={group.upcoming_session_count}
                hint={
                  group.next_session_at
                    ? `next ${formatDateTime(group.next_session_at)}`
                    : undefined
                }
              />
              <StatCard label="Completed sessions" value={group.completed_session_count} />
            </div>

            <div className="tr-tabs" role="tablist" aria-label="Group sections">
              {TABS.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  className="tr-tab"
                  aria-selected={tab === t.id}
                  onClick={() => navigate(`/trainer/groups/${group.id}?tab=${t.id}`)}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {tab === 'students' && <StudentsTab groupId={group.id} />}
            {tab === 'performance' && <PerformanceTab groupId={group.id} />}
            {tab === 'assignments' && <AssignmentsTab groupId={group.id} />}
          </>
        )}
      </Loaded>
    </TrainerPage>
  );
}

function StudentsTab({ groupId }) {
  const [filters, setFilter] = useListState({ search: '', sort: 'name' });
  const search = useDebounced(filters.search);
  const query = { ...filters, search };
  const result = useLoader(
    () => trainerApi.groupStudents(groupId, query),
    [groupId, JSON.stringify(query)],
  );

  return (
    <Section title="Students">
      <div className="tr-filters">
        <SearchInput
          label="Search students"
          placeholder="Name or email"
          value={filters.search}
          onChange={(value) => setFilter('search', value)}
        />
      </div>
      <Loaded result={result}>
        {(page) =>
          page.items.length ? (
            <>
              <DataTable
                caption="Students in this group"
                rowKey="student_id"
                rows={page.items}
                sort={filters.sort}
                onSort={(value) => setFilter('sort', value)}
                onRowClick={(row) => navigate(`/trainer/students/${row.student_id}`)}
                columns={[
                  {
                    key: 'full_name',
                    label: 'Name',
                    sortKey: 'name',
                    render: (row) => <strong>{row.full_name}</strong>,
                  },
                  { key: 'email', label: 'Email' },
                  { key: 'chess_rating', label: 'Rating', sortKey: 'rating', align: 'right' },
                  { key: 'level', label: 'Level', render: (row) => titleCase(row.level) },
                  {
                    key: 'joined_at',
                    label: 'Joined',
                    sortKey: 'joined',
                    render: (row) => formatDate(row.joined_at),
                  },
                  {
                    key: 'is_active',
                    label: 'Account',
                    render: (row) => <Status value={row.is_active ? 'active' : 'inactive'} />,
                  },
                ]}
              />
              <Pagination
                page={page.page}
                pages={page.pages}
                total={page.total}
                label="students"
                onChange={(value) => setFilter('page', value)}
              />
            </>
          ) : (
            <Empty
              title={filters.search ? 'No matching students' : 'No students in this group'}
              message={filters.search ? undefined : 'An administrator adds students to groups.'}
            />
          )
        }
      </Loaded>
    </Section>
  );
}

function PerformanceTab({ groupId }) {
  const result = useLoader(() => trainerApi.groupPerformance(groupId), [groupId]);

  return (
    <Loaded result={result}>
      {({ metrics, students }) => (
        <>
          <div className="tr-grid tr-grid--stats">
            <StatCard
              label="Puzzle accuracy"
              value={formatPercent(metrics.accuracy_percent)}
              hint={`${metrics.solved_attempts} of ${metrics.total_attempts} attempts`}
            />
            <StatCard
              label="Assignment completion"
              value={formatPercent(metrics.assignment_completion_rate)}
              hint={`${metrics.assignments_completed} of ${metrics.assignments_received}`}
            />
            <StatCard
              label="Attendance"
              value={formatPercent(metrics.attendance_rate)}
              hint={`${metrics.sessions_attended} of ${metrics.sessions_recorded} records`}
            />
            <StatCard
              label="Active students"
              value={`${metrics.active_students}/${metrics.student_count}`}
              hint="with puzzle attempts"
            />
          </div>
          <Section title="Per student">
            {students.length ? (
              <DataTable
                caption="Performance per student"
                rowKey="student_id"
                rows={students}
                onRowClick={(row) => navigate(`/trainer/students/${row.student_id}`)}
                columns={[
                  {
                    key: 'full_name',
                    label: 'Student',
                    render: (row) => <strong>{row.full_name}</strong>,
                  },
                  {
                    key: 'solved',
                    label: 'Puzzles solved',
                    align: 'right',
                    render: (row) =>
                      `${row.metrics.puzzles_solved}/${row.metrics.puzzles_attempted}`,
                  },
                  {
                    key: 'accuracy',
                    label: 'Accuracy',
                    align: 'right',
                    render: (row) => formatPercent(row.metrics.accuracy_percent),
                  },
                  {
                    key: 'completion',
                    label: 'Assignments',
                    render: (row) => (
                      <span className="tr-row">
                        <Meter
                          value={row.metrics.assignment_completion_rate}
                          label={`${row.full_name} assignment completion`}
                        />
                        {formatPercent(row.metrics.assignment_completion_rate)}
                      </span>
                    ),
                  },
                  {
                    key: 'attendance',
                    label: 'Attendance',
                    align: 'right',
                    render: (row) => formatPercent(row.metrics.attendance_rate),
                  },
                  { key: 'xp', label: 'XP', align: 'right', render: (row) => row.metrics.total_xp },
                ]}
              />
            ) : (
              <Empty title="No students in this group" />
            )}
          </Section>
        </>
      )}
    </Loaded>
  );
}

function AssignmentsTab({ groupId }) {
  const [filters, setFilter] = useListState({});
  const result = useLoader(
    () => trainerApi.groupAssignments(groupId, filters),
    [groupId, JSON.stringify(filters)],
  );

  return (
    <Section title="Assignment history">
      <Loaded result={result}>
        {(page) =>
          page.items.length ? (
            <>
              <DataTable
                caption="Assignments for this group"
                rows={page.items}
                onRowClick={(row) => navigate(`/trainer/assignments/${row.id}`)}
                columns={[
                  { key: 'title', label: 'Title', render: (row) => <strong>{row.title}</strong> },
                  {
                    key: 'status',
                    label: 'Status',
                    render: (row) => <Status value={row.status} />,
                  },
                  { key: 'puzzle_count', label: 'Puzzles', align: 'right' },
                  {
                    key: 'completed',
                    label: 'Completed',
                    align: 'right',
                    render: (row) => `${row.completed_count}/${row.recipient_count}`,
                  },
                  { key: 'due_date', label: 'Due', render: (row) => formatDate(row.due_date) },
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
              title="No assignments for this group yet"
              action={
                <ButtonLink to={`/trainer/assignments/new?group=${groupId}`} size="sm">
                  Create assignment
                </ButtonLink>
              }
            />
          )
        }
      </Loaded>
    </Section>
  );
}
