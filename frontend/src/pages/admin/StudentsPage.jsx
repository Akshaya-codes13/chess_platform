import { adminApi } from '../../features/admin/api';
import { nameColumn, statusColumn } from '../../features/admin/columns';
import UserListPage from '../../features/admin/components/UserListPage';
import { titleCase } from '../../features/trainer/format';
import { LEVEL_OPTIONS } from '../../features/admin/utils';

export default function StudentsPage() {
  return (
    <UserListPage
      title="Students"
      subtitle="Student accounts, their primary trainer and group memberships."
      noun="student"
      load={adminApi.students}
      createRole="student"
      filters={[{ name: 'level', label: 'Level', options: LEVEL_OPTIONS }]}
      columns={[
        nameColumn,
        {
          key: 'level',
          label: 'Level',
          render: (s) =>
            s.level ? titleCase(s.level) : <span className="tr-muted">No profile</span>,
        },
        {
          key: 'chess_rating',
          label: 'Rating',
          align: 'right',
          render: (s) => s.chess_rating ?? '—',
        },
        {
          key: 'trainer',
          label: 'Trainer',
          render: (s) => s.trainer?.full_name ?? <span className="tr-muted">—</span>,
        },
        { key: 'group_count', label: 'Groups', align: 'right' },
        { key: 'total_xp', label: 'XP', align: 'right' },
        statusColumn,
      ]}
    />
  );
}
