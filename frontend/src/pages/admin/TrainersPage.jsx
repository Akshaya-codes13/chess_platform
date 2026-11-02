import { adminApi } from '../../features/admin/api';
import { nameColumn, statusColumn } from '../../features/admin/columns';
import UserListPage from '../../features/admin/components/UserListPage';

export default function TrainersPage() {
  return (
    <UserListPage
      title="Trainers"
      subtitle="Trainer accounts, the groups they run and their students."
      noun="trainer"
      load={adminApi.trainers}
      createRole="trainer"
      columns={[
        nameColumn,
        {
          key: 'specialization',
          label: 'Specialization',
          render: (t) => t.specialization ?? <span className="tr-muted">—</span>,
        },
        {
          key: 'experience_years',
          label: 'Experience',
          align: 'right',
          render: (t) => (t.experience_years === null ? '—' : `${t.experience_years} yrs`),
        },
        { key: 'group_count', label: 'Groups', align: 'right' },
        { key: 'primary_student_count', label: 'Students', align: 'right' },
        statusColumn,
      ]}
    />
  );
}
