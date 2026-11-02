import { useEffect, useState } from 'react';
import { api } from '../api/client';
import Button from '../components/ui/Button';
import Tabs from '../components/ui/Tabs';
import { useAuth } from '../store/authStore';

const MODES = [
  { id: 'signin', label: 'Sign in' },
  { id: 'signup', label: 'Create account' },
];

const ROLE_LABELS = { admin: 'Admin', trainer: 'Trainer', student: 'Student' };

function describeError(err, mode) {
  if (err.status === 429) return 'Too many attempts. Wait a minute and try again.';
  if (err.status === 401) return 'That email and password do not match an active account.';
  if (err.status === 409) return 'An account with this email already exists. Sign in instead.';
  if (err.status === 422) return err.message;
  if (err.status === 404 && mode === 'demo') return err.message;
  return err.message || 'Could not reach the academy server.';
}

/** One-click sign-in to the seeded demo accounts, shown only when the API enables it. */
function DemoLogin({ busy, onPick }) {
  const [accounts, setAccounts] = useState([]);

  useEffect(() => {
    let active = true;
    api('/auth/demo')
      .then((body) => active && setAccounts(body.enabled ? body.accounts : []))
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  if (!accounts.length) return null;

  return (
    <section className="demo-login" aria-labelledby="demo-login-title">
      <h2 id="demo-login-title">Try a demo account</h2>
      <div className="demo-login-buttons">
        {accounts.map((account) => (
          <Button
            key={account.role}
            variant="secondary"
            disabled={busy}
            title={account.email}
            onClick={() => onPick(account.role)}
          >
            {ROLE_LABELS[account.role] ?? account.role}
          </Button>
        ))}
      </div>
    </section>
  );
}

export default function LoginPage() {
  const { login, register, demoLogin } = useAuth();
  const [mode, setMode] = useState('signin');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const signingUp = mode === 'signup';

  async function run(action, errorMode) {
    setSubmitting(true);
    setError('');
    try {
      await action();
    } catch (err) {
      setError(describeError(err, errorMode));
      setSubmitting(false);
    }
    // On success the router replaces this page, so there is nothing to reset.
  }

  function handleSubmit(event) {
    event.preventDefault();
    run(() => (signingUp ? register({ fullName, email, password }) : login(email, password)), mode);
  }

  function changeMode(next) {
    setMode(next);
    setError('');
  }

  const canSubmit = email && password && (!signingUp || fullName.trim().length >= 2);

  return (
    <main className="login">
      <div className="login-art" aria-hidden="true">
        <span>♞&#xFE0E;</span>
      </div>
      <form className="login-form" onSubmit={handleSubmit} noValidate>
        <h1>Chess Academy</h1>
        <p className="page-subtitle">
          {signingUp
            ? 'Create a student account to start solving puzzles.'
            : 'Sign in to see your assignments, puzzles and classes.'}
        </p>

        <Tabs tabs={MODES} value={mode} onChange={changeMode} label="Account" />

        {signingUp && (
          <label className="field">
            <span>Full name</span>
            <input
              type="text"
              autoComplete="name"
              value={fullName}
              maxLength={150}
              onChange={(e) => setFullName(e.target.value)}
              required
            />
          </label>
        )}

        <label className="field">
          <span>Email</span>
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>

        <label className="field">
          <span>Password</span>
          <input
            type="password"
            autoComplete={signingUp ? 'new-password' : 'current-password'}
            value={password}
            maxLength={128}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          {signingUp && (
            <small className="field-hint">At least 8 characters, with a letter and a digit.</small>
          )}
        </label>

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}

        <Button type="submit" disabled={submitting || !canSubmit}>
          {submitting
            ? signingUp
              ? 'Creating account…'
              : 'Signing in…'
            : signingUp
              ? 'Create account'
              : 'Sign in'}
        </Button>

        <DemoLogin busy={submitting} onPick={(role) => run(() => demoLogin(role), 'demo')} />
      </form>
    </main>
  );
}
