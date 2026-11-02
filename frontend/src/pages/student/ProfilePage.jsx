import { useState } from 'react';
import { api } from '../../api/client';
import Button from '../../components/ui/Button';
import Card from '../../components/ui/Card';
import LoadState from '../../components/ui/LoadState';
import PageHeader from '../../components/ui/PageHeader';
import { useApi } from '../../hooks/useApi';
import { formatDate, formatDateTime, titleCase } from '../../lib/format';
import { Link } from '../../routes/router';
import { useAuth } from '../../store/authStore';
import { TrainerCard } from './components';

const EDITABLE = ['full_name', 'phone', 'avatar_url', 'language', 'date_of_birth'];

function formFrom(profile) {
  return {
    full_name: profile.account.full_name ?? '',
    phone: profile.account.phone ?? '',
    avatar_url: profile.account.avatar_url ?? '',
    language: profile.account.language ?? 'en',
    date_of_birth: profile.student?.date_of_birth ?? '',
  };
}

export default function ProfilePage() {
  const { data, error, loading, reload, setData } = useApi('/student/profile');
  const { refreshUser } = useAuth();
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  if (loading || error) return <LoadState loading={loading} error={error} onRetry={reload} />;

  const editing = form !== null;

  async function save(event) {
    event.preventDefault();
    const original = formFrom(data);
    const changes = {};
    EDITABLE.forEach((key) => {
      if (form[key] !== original[key])
        changes[key] = form[key] === '' && key !== 'full_name' ? null : form[key];
    });
    if (!data.student) delete changes.date_of_birth;

    if (!Object.keys(changes).length) {
      setForm(null);
      return;
    }

    setSaving(true);
    setMessage(null);
    try {
      setData(await api('/student/profile', { method: 'PATCH', body: changes }));
      await refreshUser();
      setForm(null);
      setMessage({ tone: 'success', text: 'Profile saved.' });
    } catch (err) {
      setMessage({ tone: 'error', text: err.message });
    } finally {
      setSaving(false);
    }
  }

  const field = (key, label, props = {}) => (
    <label className="field">
      <span>{label}</span>
      <input
        value={form[key]}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
        {...props}
      />
    </label>
  );

  const { account, student } = data;

  return (
    <div className="page">
      <PageHeader
        title="Profile"
        subtitle={account.email}
        actions={
          !editing && (
            <Button variant="secondary" onClick={() => setForm(formFrom(data))}>
              Edit profile
            </Button>
          )
        }
      />

      {message && (
        <p className={message.tone === 'error' ? 'form-error' : 'form-success'} role="status">
          {message.text}
        </p>
      )}

      {editing ? (
        <Card title="Edit profile">
          <form className="form-grid" onSubmit={save}>
            {field('full_name', 'Full name', {
              required: true,
              minLength: 2,
              maxLength: 150,
              autoComplete: 'name',
            })}
            {field('phone', 'Phone', {
              type: 'tel',
              maxLength: 20,
              autoComplete: 'tel',
              placeholder: '+91 98765 43210',
            })}
            {field('avatar_url', 'Photo URL', {
              type: 'url',
              maxLength: 500,
              placeholder: 'https://…',
            })}
            <label className="field">
              <span>Language</span>
              <select
                value={form.language}
                onChange={(e) => setForm({ ...form, language: e.target.value })}
              >
                <option value="en">English</option>
                <option value="hi">Hindi</option>
                <option value="ta">Tamil</option>
                <option value="te">Telugu</option>
                <option value="kn">Kannada</option>
              </select>
            </label>
            {student && field('date_of_birth', 'Date of birth', { type: 'date' })}
            <div className="form-actions">
              <Button type="submit" disabled={saving}>
                {saving ? 'Saving…' : 'Save changes'}
              </Button>
              <Button variant="ghost" onClick={() => setForm(null)} disabled={saving}>
                Cancel
              </Button>
            </div>
            <p className="hint">
              Your email, role, rating and level are managed by the academy and cannot be changed
              here.
            </p>
          </form>
        </Card>
      ) : (
        <Card title="Account">
          <dl className="facts">
            <div>
              <dt>Name</dt>
              <dd>{account.full_name}</dd>
            </div>
            <div>
              <dt>Email</dt>
              <dd>
                {account.email}{' '}
                {account.is_verified ? '' : <span className="row-meta">(not verified)</span>}
              </dd>
            </div>
            <div>
              <dt>Phone</dt>
              <dd>{account.phone || 'Not added'}</dd>
            </div>
            <div>
              <dt>Language</dt>
              <dd>{account.language}</dd>
            </div>
            {student && (
              <>
                <div>
                  <dt>Date of birth</dt>
                  <dd>{student.date_of_birth ? formatDate(student.date_of_birth) : 'Not added'}</dd>
                </div>
                <div>
                  <dt>Level</dt>
                  <dd>{titleCase(student.level)}</dd>
                </div>
                <div>
                  <dt>Rating</dt>
                  <dd>{student.chess_rating}</dd>
                </div>
              </>
            )}
            <div>
              <dt>Member since</dt>
              <dd>{formatDate(account.created_at)}</dd>
            </div>
            <div>
              <dt>Last sign-in</dt>
              <dd>{formatDateTime(account.last_login_at)}</dd>
            </div>
          </dl>
        </Card>
      )}

      {!student && (
        <p className="hint">
          Your student profile has not been set up yet. Ask your academy to link you to a trainer.
        </p>
      )}

      <div className="two-column">
        <Card title="Trainer">
          {data.trainer ? (
            <TrainerCard trainer={data.trainer} />
          ) : (
            <p className="row-meta">No trainer assigned.</p>
          )}
        </Card>
        <Card title="Groups">
          {data.groups.length ? (
            <ul className="plain-list">
              {data.groups.map((g) => (
                <li key={g.id}>
                  <Link to={`/student/groups/${g.id}`}>{g.name}</Link>
                  <span className="row-meta"> · {g.trainer_name}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="row-meta">Not in a group yet.</p>
          )}
        </Card>
      </div>
    </div>
  );
}
