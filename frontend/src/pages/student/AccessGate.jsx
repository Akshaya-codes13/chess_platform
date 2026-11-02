import { useCallback, useEffect, useReducer } from 'react';
import { api } from '../../api/client';
import Button from '../../components/ui/Button';
import EmptyState from '../../components/ui/EmptyState';
import Spinner from '../../components/ui/Spinner';
import { navigate } from '../../routes/router';
import { useAuth } from '../../store/authStore';
import { accessReducer, initialAccess } from './access';

const timeFormat = new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' });

function WaitingScreen({ access, onRetry }) {
  const { user, logout } = useAuth();

  return (
    <main className="standalone">
      <section className="awaiting" aria-labelledby="awaiting-title">
        <div className="awaiting-mark" aria-hidden="true">
          ♟&#xFE0E;
        </div>
        <h1 id="awaiting-title">Your account is ready. Your trainer is next.</h1>
        <p className="awaiting-lead">
          Welcome{user?.full_name ? `, ${user.full_name}` : ''}! Before you can open your dashboard,
          an academy administrator needs to assign you a trainer. They will set up your classes,
          assignments and puzzles.
        </p>

        <ol className="awaiting-steps">
          <li className="is-done">
            <span className="awaiting-step-mark" aria-hidden="true">
              ✓
            </span>
            <span>
              Account created<small>{user?.email}</small>
            </span>
          </li>
          <li className="is-current">
            <span className="awaiting-step-mark" aria-hidden="true">
              2
            </span>
            <span>
              Waiting for a trainer<small>An administrator assigns one to you</small>
            </span>
          </li>
          <li>
            <span className="awaiting-step-mark" aria-hidden="true">
              3
            </span>
            <span>
              Start training<small>Your dashboard opens automatically</small>
            </span>
          </li>
        </ol>

        {access.error && (
          <p className="form-error" role="alert">
            {access.error}
          </p>
        )}

        <div className="awaiting-actions">
          <Button onClick={onRetry} disabled={access.checking}>
            {access.checking ? 'Checking…' : 'Check again'}
          </Button>
          <Button variant="ghost" onClick={logout}>
            Sign out
          </Button>
        </div>

        <p className="awaiting-status" aria-live="polite">
          {access.checking
            ? 'Checking whether a trainer has been assigned…'
            : access.checkedAt
              ? `No trainer assigned yet · last checked ${timeFormat.format(access.checkedAt)}`
              : ''}
        </p>
      </section>
    </main>
  );
}

/**
 * Shows the student portal only once the student has a trainer. Until then a
 * waiting screen explains why, and re-checks on demand or when the tab regains
 * focus, so access opens up without a new account or sign-in.
 */
export default function StudentAccessGate({ children }) {
  const [access, dispatch] = useReducer(accessReducer, initialAccess);

  const check = useCallback(async () => {
    dispatch({ type: 'check' });
    try {
      dispatch({ type: 'loaded', body: await api('/student/access'), at: new Date() });
    } catch (err) {
      dispatch({ type: 'failed', message: err.message });
    }
  }, []);

  useEffect(() => {
    check();
  }, [check]);

  const waiting = access.phase === 'waiting';

  useEffect(() => {
    if (!waiting) return undefined;
    const onFocus = () => document.visibilityState === 'visible' && check();
    document.addEventListener('visibilitychange', onFocus);
    return () => document.removeEventListener('visibilitychange', onFocus);
  }, [waiting, check]);

  useEffect(() => {
    if (access.justAssigned) navigate('/student/dashboard', { replace: true });
  }, [access.justAssigned]);

  if (access.phase === 'checking') {
    return (
      <main className="standalone">
        <Spinner label="Checking your account" />
      </main>
    );
  }

  if (access.phase === 'error') {
    return (
      <main className="standalone">
        <EmptyState
          title="We could not open your portal"
          message={access.error}
          action={<Button onClick={check}>Try again</Button>}
        />
      </main>
    );
  }

  if (waiting) return <WaitingScreen access={access} onRetry={check} />;

  return children;
}
