import { Link } from '../../../routes/router';
import { errorMessage } from '../api';
import { titleCase } from '../format';

export function PageHeader({ title, subtitle, back, actions }) {
  return (
    <header className="tr-page-header">
      <div>
        {back && (
          <Link to={back.to} className="tr-back">
            ← {back.label}
          </Link>
        )}
        <h1 className="tr-page-title">{title}</h1>
        {subtitle && <p className="tr-muted">{subtitle}</p>}
      </div>
      {actions && <div className="tr-page-actions">{actions}</div>}
    </header>
  );
}

export function Section({ title, actions, children, className = '' }) {
  return (
    <section className={`tr-card ${className}`}>
      {(title || actions) && (
        <div className="tr-card__head">
          {title && <h2 className="tr-card__title">{title}</h2>}
          {actions && <div className="tr-card__actions">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

export function StatCard({ label, value, hint, to }) {
  const body = (
    <>
      <span className="tr-stat__value">{value}</span>
      <span className="tr-stat__label">{label}</span>
      {hint && <span className="tr-stat__hint">{hint}</span>}
    </>
  );
  return to ? (
    <Link to={to} className="tr-stat tr-stat--link">
      {body}
    </Link>
  ) : (
    <div className="tr-stat">{body}</div>
  );
}

const STATUS_TONES = {
  published: 'success',
  completed: 'success',
  present: 'success',
  active: 'success',
  scheduled: 'info',
  ongoing: 'info',
  in_progress: 'info',
  draft: 'neutral',
  not_started: 'neutral',
  excused: 'neutral',
  inactive: 'neutral',
  late: 'warning',
  overdue: 'warning',
  archived: 'muted',
  cancelled: 'danger',
  absent: 'danger',
};

export function Status({ value }) {
  if (!value) return <span className="tr-muted">—</span>;
  return (
    <span className={`tr-pill tr-pill--${STATUS_TONES[value] || 'neutral'}`}>
      {titleCase(value)}
    </span>
  );
}

export function Meter({ value, label }) {
  const pct = Math.max(0, Math.min(100, value ?? 0));
  return (
    <div
      className="tr-meter"
      role="meter"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
      aria-label={label}
    >
      <div className="tr-meter__fill" style={{ width: `${pct}%` }} />
    </div>
  );
}

export function Loading({ label = 'Loading…' }) {
  return (
    <div className="tr-state" role="status">
      <span className="tr-spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function ErrorState({ error, onRetry }) {
  const notFound = error?.status === 404;
  return (
    <div className="tr-state tr-state--error" role="alert">
      <strong>{notFound ? 'Not found' : 'Could not load this page'}</strong>
      <span>
        {notFound ? 'It may have been removed, or it is not assigned to you.' : errorMessage(error)}
      </span>
      {onRetry && !notFound && (
        <button type="button" className="tr-btn tr-btn--secondary tr-btn--sm" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function Empty({ title, message, action }) {
  return (
    <div className="tr-state tr-state--empty">
      <span className="tr-state__icon" aria-hidden="true">
        ♞
      </span>
      <strong>{title}</strong>
      {message && <span className="tr-muted">{message}</span>}
      {action}
    </div>
  );
}

/** Loading / error wrapper for a useLoader result; renders children(data). */
export function Loaded({ result, children }) {
  if (result.error && !result.data)
    return <ErrorState error={result.error} onRetry={result.reload} />;
  if (!result.data) return <Loading />;
  return children(result.data);
}

export function ButtonLink({ to, children, variant = 'primary', size }) {
  return (
    <Link to={to} className={`tr-btn tr-btn--${variant}${size ? ` tr-btn--${size}` : ''}`}>
      {children}
    </Link>
  );
}

export function Button({ variant = 'primary', size, className = '', type = 'button', ...props }) {
  return (
    <button
      type={type}
      className={`tr-btn tr-btn--${variant}${size ? ` tr-btn--${size}` : ''} ${className}`}
      {...props}
    />
  );
}
