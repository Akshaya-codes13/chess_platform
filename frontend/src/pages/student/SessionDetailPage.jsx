import Card from '../../components/ui/Card';
import LoadState from '../../components/ui/LoadState';
import PageHeader from '../../components/ui/PageHeader';
import StatusBadge from '../../components/ui/StatusBadge';
import { useApi } from '../../hooks/useApi';
import { formatSessionTime, titleCase } from '../../lib/format';
import { Link, useRoute } from '../../routes/router';

export default function SessionDetailPage() {
  const { params } = useRoute();
  const { data, error, loading, reload } = useApi(`/student/sessions/${params.sessionId}`);

  if (loading || error) return <LoadState loading={loading} error={error} onRetry={reload} />;

  // Only http(s) links are rendered, so a malformed URL can never run script.
  const joinable =
    /^https?:\/\//i.test(data.meeting_url ?? '') && data.is_upcoming && data.status !== 'cancelled';

  return (
    <div className="page">
      <PageHeader
        back={{ to: '/student/sessions', label: 'Class schedule' }}
        title={data.title}
        subtitle={formatSessionTime(data.start_time, data.end_time)}
        actions={
          joinable && (
            <a
              className="btn btn-primary btn-md"
              href={data.meeting_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Join class
            </a>
          )
        }
      />

      <dl className="facts">
        <div>
          <dt>Status</dt>
          <dd>
            <StatusBadge status={data.status} />
          </dd>
        </div>
        <div>
          <dt>Trainer</dt>
          <dd>{data.trainer_name}</dd>
        </div>
        <div>
          <dt>Type</dt>
          <dd>{titleCase(data.session_type)}</dd>
        </div>
        {data.group_name && (
          <div>
            <dt>Group</dt>
            <dd>
              <Link to={`/student/groups/${data.group_id}`}>{data.group_name}</Link>
            </dd>
          </div>
        )}
        <div>
          <dt>Your attendance</dt>
          <dd>
            {data.attendance_status ? (
              <StatusBadge status={data.attendance_status} />
            ) : (
              'Not recorded yet'
            )}
            {data.attendance_remarks && (
              <span className="row-meta"> — {data.attendance_remarks}</span>
            )}
          </dd>
        </div>
      </dl>

      {data.description && (
        <Card title="About this class">
          <p className="prose">{data.description}</p>
        </Card>
      )}
      <p className="hint">
        Attendance is recorded by your trainer. Ask them if something looks wrong.
      </p>
    </div>
  );
}
