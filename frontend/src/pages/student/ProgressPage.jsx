import Button from '../../components/ui/Button';
import Card from '../../components/ui/Card';
import EmptyState from '../../components/ui/EmptyState';
import LoadState from '../../components/ui/LoadState';
import PageHeader from '../../components/ui/PageHeader';
import Pagination from '../../components/ui/Pagination';
import ProgressBar from '../../components/ui/ProgressBar';
import { useApi } from '../../hooks/useApi';
import { formatPercent, formatSeconds, titleCase } from '../../lib/format';
import { navigate, useRoute } from '../../routes/router';
import { AttemptRow, StatStrip } from './components';
import XpChart from './XpChart';

function Breakdown({ items, emptyText }) {
  if (!items.length) return <p className="row-meta">{emptyText}</p>;
  return (
    <ul className="breakdown">
      {items.map((item) => (
        <li key={item.label}>
          <span className="breakdown-label">{titleCase(item.label)}</span>
          <ProgressBar
            value={item.accuracy_percent}
            label={`${item.accuracy_percent}% · ${item.solved_attempts}/${item.attempts} attempts`}
          />
        </li>
      ))}
    </ul>
  );
}

export default function ProgressPage() {
  const { query } = useRoute();
  const page = Number(query.page) || 1;
  const { data, error, loading, reload } = useApi('/student/progress');
  const activity = useApi('/student/activity', { query: { page, page_size: 10 } });

  if (loading || error) return <LoadState loading={loading} error={error} onRetry={reload} />;

  return (
    <div className="page">
      <PageHeader
        title="Progress"
        subtitle="Calculated from every puzzle attempt you have made."
        actions={
          <Button variant="secondary" to="/student/achievements">
            XP and achievements
          </Button>
        }
      />

      <StatStrip
        items={[
          {
            label: 'Puzzles solved',
            value: data.puzzles_solved,
            hint: `of ${data.puzzles_attempted} tried`,
          },
          {
            label: 'Accuracy',
            value: formatPercent(data.accuracy_percent),
            hint: `${data.solved_attempts}/${data.total_attempts} attempts`,
          },
          { label: 'Average solve time', value: formatSeconds(data.average_solve_time_seconds) },
          {
            label: 'Assignments done',
            value: formatPercent(data.assignment_completion_percent),
            hint: `${data.assignments_completed} of ${data.assignments_total}`,
          },
          {
            label: 'Streak',
            value: `${data.current_streak} day${data.current_streak === 1 ? '' : 's'}`,
            tone: 'reward',
          },
        ]}
      />

      <Card title="XP earned per day">
        <XpChart daily={data.daily} />
      </Card>

      <div className="two-column">
        <Card title="By theme">
          <Breakdown
            items={data.themes}
            emptyText="Solve some puzzles to see which themes you are strongest in."
          />
        </Card>
        <Card title="By difficulty">
          <Breakdown items={data.difficulties} emptyText="No attempts yet." />
        </Card>
      </div>

      <Card title="Recent activity">
        <LoadState loading={activity.loading} error={activity.error} onRetry={activity.reload} />
        {activity.data &&
          (activity.data.items.length ? (
            <>
              <ul className="row-list">
                {activity.data.items.map((a) => (
                  <AttemptRow key={a.id} attempt={a} />
                ))}
              </ul>
              <Pagination
                page={activity.data.page}
                pages={activity.data.pages}
                onChange={(p) => navigate(`/student/progress?page=${p}`)}
              />
            </>
          ) : (
            <EmptyState
              title="No activity yet"
              message="Your puzzle attempts will be listed here."
            />
          ))}
      </Card>

      <details className="definitions">
        <summary>How these numbers are calculated</summary>
        <dl>
          {Object.entries(data.metric_definitions).map(([key, text]) => (
            <div key={key}>
              <dt>{titleCase(key.replace(/_percent|_seconds/g, ''))}</dt>
              <dd>{text}</dd>
            </div>
          ))}
        </dl>
      </details>
    </div>
  );
}
