const STATUS_LABELS = {
  pending: 'Not started',
  in_progress: 'In progress',
  completed: 'Completed',
  overdue: 'Overdue',
  solved: 'Solved',
  attempted: 'Not solved yet',
  not_started: 'Not started',
  failed: 'Missed',
  scheduled: 'Scheduled',
  ongoing: 'Happening now',
  cancelled: 'Cancelled',
  present: 'Present',
  late: 'Late',
  absent: 'Absent',
  excused: 'Excused',
  submitted: 'Submitted',
  graded: 'Graded',
  returned: 'Returned',
};

export function statusLabel(status) {
  return STATUS_LABELS[status] ?? status;
}

const dateFormat = new Intl.DateTimeFormat(undefined, {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
});
const dateTimeFormat = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  hour: 'numeric',
  minute: '2-digit',
});
const timeFormat = new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' });

export function formatDate(value) {
  return value ? dateFormat.format(new Date(value)) : '—';
}

export function formatDateTime(value) {
  return value ? dateTimeFormat.format(new Date(value)) : '—';
}

export function formatTime(value) {
  return value ? timeFormat.format(new Date(value)) : '';
}

export function formatSessionTime(start, end) {
  return `${formatDateTime(start)} – ${formatTime(end)}`;
}

const DAY = 24 * 60 * 60 * 1000;

/** "Due in 3 days", "Due today", "Overdue by 2 days" or "No due date". */
export function dueLabel(dueDate, status) {
  if (!dueDate) return 'No due date';
  if (status === 'completed') return `Due ${formatDate(dueDate)}`;
  const diff = new Date(dueDate).getTime() - Date.now();
  const days = Math.round(Math.abs(diff) / DAY);
  if (diff < 0) return days ? `Overdue by ${days} day${days === 1 ? '' : 's'}` : 'Overdue';
  if (days === 0) return 'Due today';
  return `Due in ${days} day${days === 1 ? '' : 's'}`;
}

export function formatSeconds(seconds) {
  if (seconds === null || seconds === undefined) return '—';
  const s = Math.round(seconds);
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, '0')}s`;
}

export function formatPercent(value) {
  return value === null || value === undefined ? '—' : `${value}%`;
}

export function titleCase(value) {
  return value ? value.charAt(0).toUpperCase() + value.slice(1).replace(/_/g, ' ') : '';
}
