import Card from '../../components/ui/Card';
import EmptyState from '../../components/ui/EmptyState';
import LoadState from '../../components/ui/LoadState';
import PageHeader from '../../components/ui/PageHeader';
import { useApi } from '../../hooks/useApi';
import { useRoute } from '../../routes/router';
import { AssignmentRow, SessionRow, TrainerCard } from './components';

export default function GroupDetailPage() {
  const { params } = useRoute();
  const { data, error, loading, reload } = useApi(`/student/groups/${params.groupId}`);

  if (loading || error) return <LoadState loading={loading} error={error} onRetry={reload} />;

  return (
    <div className="page">
      <PageHeader
        back={{ to: '/student/groups', label: 'My groups' }}
        title={data.name}
        subtitle={`${data.member_count} student${data.member_count === 1 ? '' : 's'}${data.is_active ? '' : ' · inactive group'}`}
      />
      {data.description && <p className="prose lead">{data.description}</p>}

      <div className="two-column">
        <Card title="Trainer">
          <TrainerCard trainer={data.trainer} />
        </Card>

        <Card title="Upcoming classes">
          {data.upcoming_sessions.length ? (
            <ul className="row-list">
              {data.upcoming_sessions.map((s) => (
                <SessionRow key={s.id} session={s} />
              ))}
            </ul>
          ) : (
            <EmptyState
              title="Nothing scheduled"
              message="The next class will appear here once it is planned."
            />
          )}
        </Card>
      </div>

      <Card title="Group assignments">
        {data.assignments.length ? (
          <ul className="row-list">
            {data.assignments.map((a) => (
              <AssignmentRow key={a.id} assignment={a} />
            ))}
          </ul>
        ) : (
          <EmptyState
            title="No group assignments"
            message="Assignments set for this group will be listed here."
          />
        )}
      </Card>

      <Card title="Past classes">
        {data.recent_sessions.length ? (
          <ul className="row-list">
            {data.recent_sessions.map((s) => (
              <SessionRow key={s.id} session={s} />
            ))}
          </ul>
        ) : (
          <EmptyState title="No past classes" />
        )}
      </Card>
    </div>
  );
}
