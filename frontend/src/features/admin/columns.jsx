import { Link } from '../../routes/router';
import { formatDate } from '../trainer/format';
import { ActiveStatus } from './components/shared';
import { userPath } from './utils';

// Column definitions shared by the user, trainer and student lists. The name
// is a real link so rows are reachable by keyboard.

export const nameColumn = {
  key: 'full_name',
  label: 'Name',
  render: (user) => (
    <span className="tr-stack" style={{ gap: 2 }}>
      <Link to={userPath(user)}>
        <strong>{user.full_name}</strong>
      </Link>
      <span className="tr-muted">{user.email}</span>
    </span>
  ),
};

export const statusColumn = {
  key: 'is_active',
  label: 'Status',
  render: (user) => <ActiveStatus active={user.is_active} />,
};

export const joinedColumn = {
  key: 'created_at',
  label: 'Joined',
  render: (user) => formatDate(user.created_at),
};
