import { Link } from '../../routes/router';
import { adminApi } from '../../features/admin/api';
import AdminPage from '../../features/admin/components/AdminPage';
import ActivityList from '../../features/admin/components/ActivityList';
import { ActiveStatus, Breakdown, RoleTag, UserLink } from '../../features/admin/components/shared';
import { formatDate } from '../../features/trainer/format';
import { useLoader } from '../../features/trainer/hooks';
import DataTable from '../../features/trainer/components/DataTable';
import {
  ButtonLink,
  Empty,
  Loaded,
  PageHeader,
  Section,
  StatCard,
} from '../../features/trainer/components/ui';

export default function DashboardPage() {
  const result = useLoader(() => adminApi.dashboard(), []);

  return (
    <AdminPage>
      <PageHeader
        title="Academy overview"
        subtitle="Live figures from the platform database."
        actions={<ButtonLink to="/admin/users">Manage users</ButtonLink>}
      />
      <Loaded result={result}>
        {(data) => (
          <>
            <div className="tr-grid tr-grid--stats">
              <StatCard
                label="Registered users"
                value={data.users.total}
                hint={`${data.users.active} active · ${data.users.inactive} inactive`}
                to="/admin/users"
              />
              <StatCard label="Trainers" value={data.users.trainers} to="/admin/trainers" />
              <StatCard label="Students" value={data.users.students} to="/admin/students" />
              <StatCard label="Admins" value={data.users.admins} to="/admin/users?role=admin" />
              <StatCard
                label="Groups"
                value={data.groups.total}
                hint={`${data.groups.active} active`}
                to="/admin/groups"
              />
              <StatCard label="Puzzles" value={data.puzzles} to="/admin/puzzles" />
              <StatCard
                label="Assignments"
                value={data.assignments.total}
                to="/admin/reports?tab=assignments"
              />
              <StatCard
                label="Upcoming sessions"
                value={data.sessions.upcoming}
                hint={`${data.sessions.completed} completed`}
                to="/admin/reports?tab=sessions"
              />
            </div>

            <div className="tr-split">
              <Section
                title="Recent activity"
                actions={<Link to="/admin/reports?tab=activity">View all</Link>}
              >
                <ActivityList
                  items={data.recent_activity}
                  empty="Admin actions such as creating accounts or groups appear here."
                />
              </Section>
              <Section title="Assignments by status">
                <Breakdown counts={data.assignments.by_status} label="Assignments by status" />
              </Section>
            </div>

            <div className="tr-split">
              <Section
                title="Largest active groups"
                actions={<Link to="/admin/groups">All groups</Link>}
              >
                {data.top_groups.length ? (
                  <DataTable
                    caption="Largest active groups"
                    rows={data.top_groups}
                    columns={[
                      {
                        key: 'name',
                        label: 'Group',
                        render: (g) => <Link to={`/admin/groups/${g.id}`}>{g.name}</Link>,
                      },
                      {
                        key: 'trainer',
                        label: 'Trainer',
                        render: (g) => <UserLink user={g.trainer} role="trainer" />,
                      },
                      { key: 'member_count', label: 'Students', align: 'right' },
                    ]}
                  />
                ) : (
                  <Empty
                    title="No active groups"
                    action={<ButtonLink to="/admin/groups">Create a group</ButtonLink>}
                  />
                )}
              </Section>
              <Section title="Newest users">
                {data.recent_users.length ? (
                  <DataTable
                    caption="Newest users"
                    rows={data.recent_users}
                    columns={[
                      { key: 'name', label: 'Name', render: (u) => <UserLink user={u} /> },
                      { key: 'role', label: 'Role', render: (u) => <RoleTag role={u.role} /> },
                      {
                        key: 'is_active',
                        label: 'Status',
                        render: (u) => <ActiveStatus active={u.is_active} />,
                      },
                      {
                        key: 'created_at',
                        label: 'Joined',
                        render: (u) => formatDate(u.created_at),
                      },
                    ]}
                  />
                ) : (
                  <Empty title="No users yet" />
                )}
              </Section>
            </div>
          </>
        )}
      </Loaded>
    </AdminPage>
  );
}
