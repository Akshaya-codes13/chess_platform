// Times arrive from the API in UTC (ISO 8601) and are shown in the
// viewer's local timezone.

const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' });
const dateTimeFormat = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
});
const timeFormat = new Intl.DateTimeFormat(undefined, { timeStyle: 'short' });
const weekdayFormat = new Intl.DateTimeFormat(undefined, {
  weekday: 'long',
  month: 'short',
  day: 'numeric',
});

export const formatDate = (value) => (value ? dateFormat.format(new Date(value)) : '—');
export const formatDateTime = (value) => (value ? dateTimeFormat.format(new Date(value)) : '—');
export const formatTime = (value) => (value ? timeFormat.format(new Date(value)) : '—');
export const formatWeekday = (value) => weekdayFormat.format(new Date(value));

export function formatTimeRange(start, end) {
  return `${formatDateTime(start)} – ${formatTime(end)}`;
}

/** Percent values are null when there is no data; show a dash, not 0%. */
export const formatPercent = (value) => (value === null || value === undefined ? '—' : `${value}%`);

export const localTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

/** ISO string -> value for <input type="datetime-local"> in local time. */
export function toLocalInput(value) {
  if (!value) return '';
  const date = new Date(value);
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

/** <input type="datetime-local"> value (local time) -> ISO string with offset. */
export function fromLocalInput(value) {
  return value ? new Date(value).toISOString() : null;
}

export function relativeDays(value) {
  const days = Math.round((new Date(value) - Date.now()) / 86400000);
  if (days === 0) return 'today';
  if (days === 1) return 'tomorrow';
  if (days === -1) return 'yesterday';
  return days > 0 ? `in ${days} days` : `${-days} days ago`;
}

export const sideToMove = (fen) => (fen?.split(' ')[1] === 'b' ? 'Black' : 'White');

export const titleCase = (value) =>
  (value || '').replace(/[_-]/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());

export const DIFFICULTIES = ['beginner', 'intermediate', 'advanced'].map((value) => ({
  value,
  label: titleCase(value),
}));
