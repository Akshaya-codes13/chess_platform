import { Link } from '../../../routes/router';
import { titleCase } from '../../trainer/format';
import { Meter, Status } from '../../trainer/components/ui';
import { userPath } from '../utils';

export function ActiveStatus({ active }) {
  return <Status value={active ? 'active' : 'inactive'} />;
}

export function RoleTag({ role }) {
  return <span className="tr-tag">{titleCase(role)}</span>;
}

export function UserLink({ user, role }) {
  if (!user) return <span className="tr-muted">—</span>;
  return <Link to={userPath({ ...user, role: role ?? user.role })}>{user.full_name}</Link>;
}

/** Labelled horizontal bars for a { key: count } breakdown. */
export function Breakdown({ counts, label }) {
  const entries = Object.entries(counts ?? {}).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map(([, count]) => count));

  if (!entries.length) return <p className="tr-muted">No records yet.</p>;

  return (
    <ul className="ad-breakdown" aria-label={label}>
      {entries.map(([key, count]) => (
        <li key={key}>
          <span>{titleCase(key)}</span>
          <Meter value={(100 * count) / max} label={`${titleCase(key)}: ${count}`} />
          <span className="ad-breakdown__count">{count}</span>
        </li>
      ))}
    </ul>
  );
}
