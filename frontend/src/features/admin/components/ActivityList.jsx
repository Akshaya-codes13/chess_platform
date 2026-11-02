import { Link } from '../../../routes/router';
import { formatDateTime } from '../../trainer/format';
import { Empty } from '../../trainer/components/ui';
import { activityLabel, entityPath } from '../utils';

export default function ActivityList({ items, empty }) {
  if (!items.length) return <Empty title="No activity yet" message={empty} />;

  return (
    <ul className="ad-activity">
      {items.map((item) => {
        const path = entityPath(item.entity_type, item.entity_id);
        const label = activityLabel(item.action);
        return (
          <li key={item.id}>
            <span>
              {path ? <Link to={path}>{label}</Link> : label}
              <span className="tr-muted"> by {item.actor?.full_name ?? 'a removed user'}</span>
            </span>
            <time className="tr-muted" dateTime={item.occurred_at}>
              {formatDateTime(item.occurred_at)}
            </time>
          </li>
        );
      })}
    </ul>
  );
}
