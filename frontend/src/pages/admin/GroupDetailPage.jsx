import { useState } from 'react';
import { Link, useRoute } from '../../routes/router';
import { adminApi } from '../../features/admin/api';
import AdminPage from '../../features/admin/components/AdminPage';
import {
  AddStudentsDialog,
  AssignTrainerDialog,
  GroupDialog,
} from '../../features/admin/components/GroupDialogs';
import { ActiveStatus, UserLink } from '../../features/admin/components/shared';
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
} from '../../features/trainer/components/ui';
import { formatDate, titleCase } from '../../features/trainer/format';
import { useLoader } from '../../features/trainer/hooks';

export default function GroupDetailPage() {
  const { params } = useRoute();
  const result = useLoader(() => adminApi.group(params.groupId), [params.groupId]);
  const [dialog, setDialog] = useState(null);
  const [removing, setRemoving] = useState(null);
  const [busy, setBusy] = useState(false);
  const group = result.data;

  async function removeStudent() {
    setBusy(true);
    const ok = await runAction(
      () => adminApi.removeStudent(group.id, removing.id),
      `${removing.full_name} was removed from the group.`,
    );
    setBusy(false);
    setRemoving(null);
    if (ok) result.reload();
  }

  return (
    <AdminPage>
      <Loaded result={result}>
        {(data) => (
          <>
            <PageHeader
              back={{ to: '/admin/groups', label: 'Groups' }}
              title={data.name}
              subtitle={data.description || 'No description.'}
              actions={
                <>
                  <Button variant="secondary" onClick={() => setDialog('edit')}>
                    Edit group
                  </Button>
                  <Button variant="secondary" onClick={() => setDialog('trainer')}>
                    Change trainer
                  </Button>
                  <Button onClick={() => setDialog('students')}>Add students</Button>
                </>
              }
            />
            <div className="tr-grid tr-grid--stats">
              <StatCard label="Students" value={data.member_count} />
              <StatCard label="Upcoming sessions" value={data.upcoming_session_count} />
              <StatCard label="Assignments" value={data.assignment_count} />
            </div>
            <Section title="Details">
              <dl className="ad-dl">
                <dt>Trainer</dt>
                <dd>
                  <UserLink user={data.trainer} role="trainer" />
                </dd>
                <dt>Status</dt>
                <dd>
                  <ActiveStatus active={data.is_active} />
                </dd>
                <dt>Created</dt>
                <dd>{formatDate(data.created_at)}</dd>
              </dl>
            </Section>
            <Section
              title={`Members (${data.members.length})`}
              actions={<Link to={`/admin/reports?tab=sessions&group_id=${data.id}`}>Sessions</Link>}
            >
              {data.members.length ? (
                <DataTable
                  caption="Group members"
                  rows={data.members}
                  columns={[
                    {
                      key: 'full_name',
                      label: 'Student',
                      render: (m) => (
                        <span className="tr-stack" style={{ gap: 2 }}>
                          <Link to={`/admin/students/${m.id}`}>
                            <strong>{m.full_name}</strong>
                          </Link>
                          <span className="tr-muted">{m.email}</span>
                        </span>
                      ),
                    },
                    { key: 'level', label: 'Level', render: (m) => titleCase(m.level) },
                    { key: 'chess_rating', label: 'Rating', align: 'right' },
                    {
                      key: 'is_active',
                      label: 'Account',
                      render: (m) => <ActiveStatus active={m.is_active} />,
                    },
                    { key: 'joined_at', label: 'Joined', render: (m) => formatDate(m.joined_at) },
                    {
                      key: 'actions',
                      label: 'Actions',
                      align: 'right',
                      render: (m) => (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setRemoving(m)}
                          aria-label={`Remove ${m.full_name} from ${data.name}`}
                        >
                          Remove
                        </Button>
                      ),
                    },
                  ]}
                />
              ) : (
                <Empty
                  title="No students yet"
                  action={<Button onClick={() => setDialog('students')}>Add students</Button>}
                />
              )}
            </Section>

            <GroupDialog
              key={`edit-${data.updated_at}`}
              open={dialog === 'edit'}
              group={data}
              onClose={() => setDialog(null)}
              onSaved={() => result.reload()}
            />
            <AssignTrainerDialog
              open={dialog === 'trainer'}
              group={data}
              onClose={() => setDialog(null)}
              onSaved={() => result.reload()}
            />
            <AddStudentsDialog
              open={dialog === 'students'}
              group={data}
              onClose={() => setDialog(null)}
              onSaved={() => result.reload()}
            />
            <ConfirmDialog
              open={Boolean(removing)}
              title="Remove student?"
              message={
                removing &&
                `${removing.full_name} will leave ${data.name}. Their account, progress and past submissions are kept.`
              }
              confirmLabel="Remove"
              tone="danger"
              busy={busy}
              onConfirm={removeStudent}
              onCancel={() => setRemoving(null)}
            />
          </>
        )}
      </Loaded>
    </AdminPage>
  );
}
