import EmptyState from '../../components/ui/EmptyState';
import LoadState from '../../components/ui/LoadState';
import PageHeader from '../../components/ui/PageHeader';
import Pagination from '../../components/ui/Pagination';
import StatusBadge from '../../components/ui/StatusBadge';
import { useApi } from '../../hooks/useApi';
import { formatPercent, formatSessionTime } from '../../lib/format';
import { Link, navigate, useRoute } from '../../routes/router';
import { StatStrip } from './components';

export default function AttendancePage() {
  const { query } = useRoute();
  const page = Number(query.page) || 1;
  const { data, error, loading, reload } = useApi('/student/attendance', {
    query: { page, page_size: 20 },
  });

  return (
    <div className="page">
      <PageHeader
        back={{ to: '/student/sessions', label: 'Class schedule' }}
        title="Attendance history"
        subtitle="Recorded by your trainer after each class."
      />
      <LoadState loading={loading} error={error} onRetry={reload} />
      {data && (
        <>
          <StatStrip
            items={[
              {
                label: 'Attendance rate',
                value: formatPercent(data.summary.attendance_rate_percent),
                hint: 'Present or late, out of classes marked present, late or absent',
              },
              { label: 'Present', value: data.summary.present },
              { label: 'Late', value: data.summary.late },
              { label: 'Absent', value: data.summary.absent },
              { label: 'Excused', value: data.summary.excused },
            ]}
          />
          {data.items.length ? (
            <div className="table-wrap">
              <table className="table">
                <caption className="visually-hidden">Your attendance by class</caption>
                <thead>
                  <tr>
                    <th scope="col">Class</th>
                    <th scope="col">When</th>
                    <th scope="col">Trainer</th>
                    <th scope="col">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((row) => (
                    <tr key={row.session_id}>
                      <td>
                        <Link to={`/student/sessions/${row.session_id}`}>{row.session_title}</Link>
                        {row.remarks && <span className="row-meta cell-note">{row.remarks}</span>}
                      </td>
                      <td>{formatSessionTime(row.start_time, row.end_time)}</td>
                      <td>{row.trainer_name}</td>
                      <td>
                        <StatusBadge
                          status={row.status}
                          label={row.status === 'scheduled' ? 'Not recorded' : undefined}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              title="No attendance recorded"
              message="Your attendance appears here after your first class."
            />
          )}
          <Pagination
            page={data.page}
            pages={data.pages}
            onChange={(p) => navigate(`/student/attendance?page=${p}`)}
          />
        </>
      )}
    </div>
  );
}
