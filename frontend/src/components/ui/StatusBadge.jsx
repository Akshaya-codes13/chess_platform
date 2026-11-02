import { statusLabel } from '../../lib/format';

/** Coloured label for assignment, puzzle, session and attendance statuses. */
export default function StatusBadge({ status, label }) {
  return <span className={`status status-${status}`}>{label ?? statusLabel(status)}</span>;
}
