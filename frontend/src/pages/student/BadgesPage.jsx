import EmptyState from '../../components/ui/EmptyState';
import LoadState from '../../components/ui/LoadState';
import PageHeader from '../../components/ui/PageHeader';
import { useApi } from '../../hooks/useApi';
import { BadgeTile } from './components';

export default function BadgesPage() {
  const { data, error, loading, reload } = useApi('/student/badges');

  if (loading || error) return <LoadState loading={loading} error={error} onRetry={reload} />;

  const earned = data.filter((b) => b.earned);
  const locked = data.filter((b) => !b.earned);

  return (
    <div className="page">
      <PageHeader
        back={{ to: '/student/achievements', label: 'XP and achievements' }}
        title="Badge collection"
        subtitle={`${earned.length} of ${data.length} earned`}
      />
      {!data.length && (
        <EmptyState title="No badges available" message="The academy has not set up badges yet." />
      )}
      {earned.length > 0 && (
        <section aria-labelledby="earned-title">
          <h2 id="earned-title" className="subheading">
            Earned
          </h2>
          <ul className="badge-grid">
            {earned.map((b) => (
              <BadgeTile key={b.id} badge={b} />
            ))}
          </ul>
        </section>
      )}
      {locked.length > 0 && (
        <section aria-labelledby="locked-title">
          <h2 id="locked-title" className="subheading">
            Still to earn
          </h2>
          <ul className="badge-grid">
            {locked.map((b) => (
              <BadgeTile key={b.id} badge={b} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
