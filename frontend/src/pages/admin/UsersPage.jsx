import { adminApi } from '../../features/admin/api';
import { RoleTag } from '../../features/admin/components/shared';
import { joinedColumn, nameColumn, statusColumn } from '../../features/admin/columns';
import UserListPage from '../../features/admin/components/UserListPage';
import { formatDateTime } from '../../features/trainer/format';
import { ROLE_OPTIONS } from '../../features/admin/utils';

export default function UsersPage() {
  return (
    <UserListPage
      title="Users"
      subtitle="Every account on the platform. Open one to edit it, change its role or deactivate it."
      noun="user"
      load={adminApi.users}
      createRole={null}
      createLabel="New account"
      filters={[{ name: 'role', label: 'Role', options: ROLE_OPTIONS }]}
      columns={[
        nameColumn,
        { key: 'role', label: 'Role', render: (user) => <RoleTag role={user.role} /> },
        statusColumn,
        {
          key: 'last_login_at',
          label: 'Last sign-in',
          render: (user) => formatDateTime(user.last_login_at),
        },
        joinedColumn,
      ]}
    />
  );
}
