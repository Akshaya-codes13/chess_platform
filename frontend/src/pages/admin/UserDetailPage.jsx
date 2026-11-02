import { useState } from 'react';
import { Link, useRoute } from '../../routes/router';
import { useAuth } from '../../store/authStore';
import { adminApi } from '../../features/admin/api';
import AdminPage from '../../features/admin/components/AdminPage';
import { ActiveStatus, RoleTag, UserLink } from '../../features/admin/components/shared';
import { EditUserDialog, RoleDialog } from '../../features/admin/components/UserDialogs';
import { runAction } from '../../features/admin/utils';
import ConfirmDialog from '../../features/trainer/components/ConfirmDialog';
import DataTable from '../../features/trainer/components/DataTable';
import {
  Button,
  Empty,
  Loaded,
  PageHeader,
  Section,
  StatCard,
  Status,
} from '../../features/trainer/components/ui';
import { formatDate, formatDateTime, titleCase } from '../../features/trainer/format';
import { useLoader } from '../../features/trainer/hooks';

const BACK = {
  trainer: { to: '/admin/trainers', label: 'Trainers' },
  student: { to: '/admin/students', label: 'Students' },
  admin: { to: '/admin/users', label: 'Users' },
};

function Details({ items }) {
  return (
    <dl className="ad-dl">
      {items.map(([label, value]) => (
        <div key={label} style={{ display: 'contents' }}>
          <dt>{label}</dt>
          <dd>{value ?? <span className="tr-muted">—</span>}</dd>
        </div>
      ))}
    </dl>
  );
}

function GroupsTable({ groups, empty }) {
  if (!groups.length) return <Empty title="No groups" message={empty} />;
  return (
    <DataTable
      caption="Groups"
      rows={groups}
      columns={[
        {
          key: 'name',
          label: 'Group',
          render: (g) => <Link to={`/admin/groups/${g.id}`}>{g.name}</Link>,
        },
        {
          key: 'is_active',
          label: 'Status',
          render: (g) => <ActiveStatus active={g.is_active} />,
        },
      ]}
    />
  );
}

function TrainerSections({ user }) {
  const profile = user.trainer_profile;
  const stats = user.trainer_stats;
  return (
    <>
      <Section title="Trainer profile">
        {profile ? (
          <Details
            items={[
              ['Specialization', profile.specialization],
              ['Experience', `${profile.experience_years} years`],
              ['Bio', profile.bio],
            ]}
          />
        ) : (
          <p className="tr-muted">No trainer profile yet. Edit the account to create one.</p>
        )}
      </Section>
      {stats && (
        <div className="tr-grid tr-grid--stats">
          <StatCard
            label="Groups"
            value={stats.group_count}
            hint={`${stats.active_group_count} active`}
          />
          <StatCard label="Primary students" value={stats.primary_student_count} />
          <StatCard label="Students in groups" value={stats.group_student_count} />
          <StatCard label="Upcoming sessions" value={stats.upcoming_session_count} />
          <StatCard label="Assignments" value={stats.assignment_count} />
        </div>
      )}
      <Section
        title="Groups run by this trainer"
        actions={<Link to={`/admin/groups?trainer_id=${user.id}`}>Manage groups</Link>}
      >
        <GroupsTable groups={user.groups} empty="Assign this trainer to a group from its page." />
      </Section>
    </>
  );
}

function StudentSections({ user }) {
  const profile = user.student_profile;
  const progress = user.student_progress;
  return (
    <>
      <Section title="Student profile">
        {profile ? (
          <Details
            items={[
              ['Primary trainer', <UserLink key="t" user={profile.trainer} role="trainer" />],
              ['Level', titleCase(profile.level)],
              ['Chess rating', profile.chess_rating],
              ['Date of birth', profile.date_of_birth && formatDate(profile.date_of_birth)],
              ['Notes', profile.notes],
            ]}
          />
        ) : (
          <p className="tr-callout tr-callout--info">
            This student registered without a profile. Edit the account and choose a primary trainer
            so they can join groups.
          </p>
        )}
      </Section>
      {progress && (
        <div className="tr-grid tr-grid--stats">
          <StatCard label="Total XP" value={progress.total_xp} />
          <StatCard
            label="Current streak"
            value={progress.current_streak}
            hint={`Longest ${progress.longest_streak}`}
          />
          <StatCard label="Puzzles solved" value={progress.puzzles_solved} />
          <StatCard label="Games played" value={progress.games_played} />
        </div>
      )}
      <Section title="Groups" actions={<Link to="/admin/groups">Manage groups</Link>}>
        <GroupsTable
          groups={user.groups}
          empty="Add this student to a group from the group's page."
        />
      </Section>
      <Section title="Assignments">
        {user.assignments.length ? (
          <DataTable
            caption="Assignments"
            rows={user.assignments}
            columns={[
              { key: 'title', label: 'Assignment' },
              { key: 'status', label: 'Status', render: (a) => <Status value={a.status} /> },
              {
                key: 'trainer',
                label: 'Trainer',
                render: (a) => <UserLink user={a.trainer} role="trainer" />,
              },
              { key: 'due_date', label: 'Due', render: (a) => formatDate(a.due_date) },
              {
                key: 'latest',
                label: 'Latest submission',
                render: (a) =>
                  a.latest_submission_status ? (
                    <>
                      <Status value={a.latest_submission_status} />
                      {a.latest_score !== null && ` ${a.latest_score} pts`}
                    </>
                  ) : (
                    <span className="tr-muted">None</span>
                  ),
              },
              { key: 'attempts', label: 'Attempts', align: 'right' },
            ]}
          />
        ) : (
          <Empty title="No assignments" message="Trainers assign work to students." />
        )}
      </Section>
    </>
  );
}

export default function UserDetailPage() {
  const { params } = useRoute();
  const { user: me } = useAuth();
  const result = useLoader(() => adminApi.user(params.userId), [params.userId]);
  const [dialog, setDialog] = useState(null);
  const [busy, setBusy] = useState(false);
  const user = result.data;
  const isSelf = user && me && user.id === me.id;

  async function toggleStatus() {
    setBusy(true);
    const saved = await runAction(
      () => adminApi.changeStatus(user.id, !user.is_active),
      user.is_active ? `${user.full_name} was deactivated.` : `${user.full_name} was activated.`,
    );
    setBusy(false);
    setDialog(null);
    if (saved) result.reload();
  }

  return (
    <AdminPage>
      <Loaded result={result}>
        {(data) => (
          <>
            <PageHeader
              back={BACK[data.role]}
              title={data.full_name}
              subtitle={
                <span className="tr-row" style={{ gap: 8 }}>
                  <RoleTag role={data.role} />
                  <ActiveStatus active={data.is_active} />
                  {isSelf && <span className="tr-muted">This is your account</span>}
                </span>
              }
              actions={
                <>
                  <Button variant="secondary" onClick={() => setDialog('edit')}>
                    Edit profile
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => setDialog('role')}
                    disabled={isSelf}
                    title={isSelf ? 'You cannot change your own role.' : undefined}
                  >
                    Change role
                  </Button>
                  <Button
                    variant={data.is_active ? 'danger' : 'primary'}
                    onClick={() => setDialog('status')}
                    disabled={isSelf}
                    title={isSelf ? 'You cannot deactivate your own account.' : undefined}
                  >
                    {data.is_active ? 'Deactivate' : 'Activate'}
                  </Button>
                </>
              }
            />
            <Section title="Account">
              <Details
                items={[
                  ['Email', data.email],
                  ['Email verified', data.is_verified ? 'Yes' : 'No'],
                  ['Phone', data.phone],
                  ['Language', data.language],
                  ['Last sign-in', data.last_login_at && formatDateTime(data.last_login_at)],
                  ['Joined', formatDate(data.created_at)],
                ]}
              />
            </Section>
            {data.role === 'trainer' && <TrainerSections user={data} />}
            {data.role === 'student' && <StudentSections user={data} />}

            <EditUserDialog
              key={`edit-${data.updated_at}`}
              open={dialog === 'edit'}
              user={data}
              onClose={() => setDialog(null)}
              onSaved={() => result.reload()}
            />
            {!isSelf && (
              <RoleDialog
                key={`role-${data.role}`}
                open={dialog === 'role'}
                user={data}
                onClose={() => setDialog(null)}
                onSaved={() => result.reload()}
              />
            )}
            <ConfirmDialog
              open={dialog === 'status'}
              title={
                data.is_active ? `Deactivate ${data.full_name}?` : `Activate ${data.full_name}?`
              }
              message={
                data.is_active
                  ? 'They are signed out everywhere and cannot sign in until reactivated. Their data is kept.'
                  : 'They can sign in again with their existing password.'
              }
              confirmLabel={data.is_active ? 'Deactivate' : 'Activate'}
              tone={data.is_active ? 'danger' : 'primary'}
              busy={busy}
              onConfirm={toggleStatus}
              onCancel={() => setDialog(null)}
            />
          </>
        )}
      </Loaded>
    </AdminPage>
  );
}
