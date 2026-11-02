import EmptyState from '../../components/ui/EmptyState';
import LoadState from '../../components/ui/LoadState';
import PageHeader from '../../components/ui/PageHeader';
import { useApi } from '../../hooks/useApi';
import { formatDate } from '../../lib/format';
import { Link } from '../../routes/router';

export default function GroupsPage() {
  const { data, error, loading, reload } = useApi('/student/groups', { query: { page_size: 100 } });

  return (
    <div className="page">
      <PageHeader
        title="My groups"
        subtitle="The training groups you belong to and who coaches them."
      />
      <LoadState loading={loading} error={error} onRetry={reload} />
      {data &&
        (data.items.length ? (
          <ul className="group-list">
            {data.items.map((group) => (
              <li key={group.id}>
                <Link to={`/student/groups/${group.id}`} className="group-item">
                  <span className="row-title">{group.name}</span>
                  {!group.is_active && <span className="status status-cancelled">Inactive</span>}
                  {group.description && <span className="row-meta">{group.description}</span>}
                  <span className="row-meta">
                    Coached by {group.trainer.full_name} · {group.member_count} student
                    {group.member_count === 1 ? '' : 's'} · joined {formatDate(group.joined_at)}
                  </span>
                  <span className="row-meta">
                    {group.upcoming_session_count
                      ? `${group.upcoming_session_count} upcoming class${group.upcoming_session_count === 1 ? '' : 'es'}`
                      : 'No upcoming classes'}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState
            title="You are not in a group yet"
            message="Your trainer or academy adds you to groups."
          />
        ))}
    </div>
  );
}
