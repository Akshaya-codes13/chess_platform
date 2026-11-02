import EmptyState from '../../components/ui/EmptyState';
import LoadState from '../../components/ui/LoadState';
import PageHeader from '../../components/ui/PageHeader';
import Pagination from '../../components/ui/Pagination';
import Tabs from '../../components/ui/Tabs';
import { useApi } from '../../hooks/useApi';
import { navigate, useRoute } from '../../routes/router';
import { AssignmentRow } from './components';

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'pending', label: 'Not started' },
  { id: 'in_progress', label: 'In progress' },
  { id: 'overdue', label: 'Overdue' },
  { id: 'completed', label: 'Completed' },
];

const EMPTY_MESSAGES = {
  all: 'Your trainer has not assigned any work yet.',
  pending: 'Every assignment has been started.',
  in_progress: 'Nothing is half-finished.',
  overdue: 'Nothing is past its due date.',
  completed: 'Completed assignments will be listed here.',
};

export default function AssignmentsPage() {
  const { query } = useRoute();
  const filter = FILTERS.some((f) => f.id === query.status) ? query.status : 'all';
  const page = Number(query.page) || 1;

  const { data, error, loading, reload } = useApi('/student/assignments', {
    query: { status: filter === 'all' ? null : filter, page, page_size: 20 },
  });

  function go(nextFilter, nextPage = 1) {
    const params = new URLSearchParams();
    if (nextFilter !== 'all') params.set('status', nextFilter);
    if (nextPage > 1) params.set('page', nextPage);
    const qs = params.toString();
    navigate(`/student/assignments${qs ? `?${qs}` : ''}`);
  }

  return (
    <div className="page">
      <PageHeader
        title="Assignments"
        subtitle="Puzzle sets from your trainer. Progress updates as you solve."
      />
      <Tabs tabs={FILTERS} value={filter} onChange={(id) => go(id)} label="Assignment status" />

      <LoadState loading={loading} error={error} onRetry={reload} />
      {data &&
        (data.items.length ? (
          <>
            <ul className="row-list">
              {data.items.map((a) => (
                <AssignmentRow key={a.id} assignment={a} />
              ))}
            </ul>
            <Pagination page={data.page} pages={data.pages} onChange={(p) => go(filter, p)} />
          </>
        ) : (
          <EmptyState title="No assignments here" message={EMPTY_MESSAGES[filter]} />
        ))}
    </div>
  );
}
