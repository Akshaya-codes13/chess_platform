import { useState } from 'react';
import { useAuth } from '../../store/authStore';
import { errorMessage, fieldErrors, trainerApi } from '../../features/trainer/api';
import { formatDate, formatDateTime } from '../../features/trainer/format';
import { useLoader } from '../../features/trainer/hooks';
import TrainerPage from '../../features/trainer/components/TrainerPage';
import ConfirmDialog from '../../features/trainer/components/ConfirmDialog';
import { TextArea, TextField } from '../../features/trainer/components/Field';
import { toast } from '../../features/trainer/components/toastStore';
import { Button, Loaded, PageHeader, Section, Status } from '../../features/trainer/components/ui';

export default function ProfilePage() {
  const result = useLoader(() => trainerApi.profile(), []);

  return (
    <TrainerPage>
      <PageHeader
        title="My profile"
        subtitle="Your role, email and account status are managed by an administrator."
      />
      <Loaded result={result}>
        {(profile) => (
          <Profile
            key={profile.full_name + profile.bio}
            profile={profile}
            onSaved={result.reload}
          />
        )}
      </Loaded>
    </TrainerPage>
  );
}

function Profile({ profile, onSaved }) {
  const { refreshUser } = useAuth();
  const [form, setForm] = useState({
    full_name: profile.full_name,
    phone: profile.phone ?? '',
    specialization: profile.specialization ?? '',
    experience_years: String(profile.experience_years),
    bio: profile.bio ?? '',
  });
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);
  const [resetBusy, setResetBusy] = useState(false);

  const set = (name) => (value) => {
    setForm((current) => ({ ...current, [name]: value }));
    setErrors((current) => ({ ...current, [name]: undefined, form: undefined }));
  };

  async function submit(event) {
    event.preventDefault();
    const next = {};
    if (form.full_name.trim().length < 2) next.full_name = 'Name must be at least 2 characters.';
    const years = Number(form.experience_years);
    if (!Number.isInteger(years) || years < 0 || years > 80)
      next.experience_years = 'Enter a whole number between 0 and 80.';
    if (form.phone && !/^\+?[0-9 ()-]{6,20}$/.test(form.phone))
      next.phone = 'Use 6–20 digits, spaces, dashes or brackets.';
    if (Object.keys(next).length) {
      setErrors(next);
      return;
    }

    setSaving(true);
    try {
      await trainerApi.updateProfile({
        full_name: form.full_name.trim(),
        phone: form.phone.trim() || null,
        specialization: form.specialization.trim() || null,
        experience_years: years,
        bio: form.bio.trim() || null,
      });
      toast.success('Profile updated.');
      await refreshUser();
      onSaved();
    } catch (error) {
      setErrors({ ...fieldErrors(error), form: errorMessage(error) });
    } finally {
      setSaving(false);
    }
  }

  async function requestReset() {
    setResetBusy(true);
    try {
      await trainerApi.requestPasswordReset(profile.email);
      toast.info('Password reset requested. Follow the link sent to your email.');
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setResetBusy(false);
      setResetOpen(false);
    }
  }

  return (
    <div className="tr-split">
      <Section title="Profile details">
        <form className="tr-form" onSubmit={submit} noValidate>
          {errors.form && (
            <p className="tr-callout tr-callout--error" role="alert">
              {errors.form}
            </p>
          )}
          <TextField
            label="Full name"
            required
            value={form.full_name}
            onChange={set('full_name')}
            error={errors.full_name}
            maxLength={150}
            autoComplete="name"
          />
          <div className="tr-form-grid">
            <TextField
              label="Phone"
              type="tel"
              value={form.phone}
              onChange={set('phone')}
              error={errors.phone}
              autoComplete="tel"
            />
            <TextField
              label="Years of experience"
              type="number"
              min="0"
              max="80"
              value={form.experience_years}
              onChange={set('experience_years')}
              error={errors.experience_years}
            />
          </div>
          <TextField
            label="Specialization"
            value={form.specialization}
            onChange={set('specialization')}
            error={errors.specialization}
            maxLength={150}
            placeholder="e.g. Endgames, junior training"
          />
          <TextArea
            label="Bio"
            value={form.bio}
            onChange={set('bio')}
            error={errors.bio}
            rows={5}
            maxLength={2000}
          />
          <div className="tr-form-actions">
            <Button type="submit" disabled={saving}>
              {saving ? 'Saving…' : 'Save profile'}
            </Button>
          </div>
        </form>
      </Section>
      <div className="tr-stack">
        <Section title="Account">
          <dl className="tr-stack" style={{ margin: 0 }}>
            <div>
              <dt className="tr-field__label">Email</dt>
              <dd style={{ margin: 0 }}>{profile.email}</dd>
            </div>
            <div>
              <dt className="tr-field__label">Role</dt>
              <dd style={{ margin: 0 }}>Trainer</dd>
            </div>
            <div>
              <dt className="tr-field__label">Status</dt>
              <dd style={{ margin: 0 }} className="tr-row">
                <Status value={profile.is_active ? 'active' : 'inactive'} />
                {!profile.is_verified && <span className="tr-muted">email not verified</span>}
              </dd>
            </div>
            <div>
              <dt className="tr-field__label">Member since</dt>
              <dd style={{ margin: 0 }}>{formatDate(profile.created_at)}</dd>
            </div>
            <div>
              <dt className="tr-field__label">Last sign-in</dt>
              <dd style={{ margin: 0 }}>{formatDateTime(profile.last_login_at)}</dd>
            </div>
          </dl>
        </Section>
        <Section title="Password">
          <p className="tr-muted" style={{ marginTop: 0 }}>
            Passwords are changed through the secure reset flow: we send a single-use link to your
            email address.
          </p>
          <Button variant="secondary" onClick={() => setResetOpen(true)}>
            Send password reset link
          </Button>
        </Section>
      </div>
      <ConfirmDialog
        open={resetOpen}
        title="Send a password reset link?"
        message={`A reset link will be sent to ${profile.email}. Your current password keeps working until you set a new one.`}
        confirmLabel="Send link"
        busy={resetBusy}
        onConfirm={requestReset}
        onCancel={() => setResetOpen(false)}
      />
    </div>
  );
}
