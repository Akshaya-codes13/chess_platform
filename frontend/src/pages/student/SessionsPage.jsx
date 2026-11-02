import Button from '../../components/ui/Button';
import EmptyState from '../../components/ui/EmptyState';
import LoadState from '../../components/ui/LoadState';
import PageHeader from '../../components/ui/PageHeader';
import Pagination from '../../components/ui/Pagination';
import Tabs from '../../components/ui/Tabs';
import { useApi } from '../../hooks/useApi';
import { navigate, useRoute } from '../../routes/router';
import { SessionRow } from './components';

const SCOPES = [
  { id: 'upcoming', label: 'Upcoming' },
  { id: 'past', label: 'Past' },
  { id: 'all', label: 'All' },
];

export default function SessionsPage() {
  const { query } = useRoute();
  const scope = SCOPES.some((s) => s.id === query.scope) ? query.scope : 'upcoming';
  const page = Number(query.page) || 1;
  const { data, error, loading, reload } = useApi('/student/sessions', {
    query: { scope, page, page_size: 20 },
  });

  const go = (nextScope, nextPage = 1) =>
    navigate(`/student/sessions?scope=${nextScope}${nextPage > 1 ? `&page=${nextPage}` : ''}`);

  return (
    <div className="page">
      <PageHeader
        title="Class schedule"
        subtitle="Classes for your groups and any one-to-one lessons."
        actions={
          <Button variant="secondary" to="/student/attendance">
            Attendance history
          </Button>
        }
      />
      <Tabs tabs={SCOPES} value={scope} onChange={(id) => go(id)} label="Which classes" />
      <LoadState loading={loading} error={error} onRetry={reload} />
      {data &&
        (data.items.length ? (
          <>
            <ul className="row-list">
              {data.items.map((s) => (
                <SessionRow key={s.id} session={s} />
              ))}
            </ul>
            <Pagination page={data.page} pages={data.pages} onChange={(p) => go(scope, p)} />
          </>
        ) : (
          <EmptyState
            title={scope === 'upcoming' ? 'No classes coming up' : 'No classes yet'}
            message={
              scope === 'upcoming' ? 'Your trainer has not scheduled the next class.' : undefined
            }
          />
        ))}
    </div>
  );
}
