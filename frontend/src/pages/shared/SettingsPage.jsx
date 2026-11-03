import { useState } from 'react';
import ChessBoard from '../../components/chess/ChessBoard';
import { errorMessage, fieldErrors } from '../../features/trainer/api';
import { SelectField, TextField } from '../../features/trainer/components/Field';
import TrainerPage from '../../features/trainer/components/TrainerPage';
import { toast } from '../../features/trainer/components/toastStore';
import { Button, Loaded, PageHeader, Section } from '../../features/trainer/components/ui';
import { useLoader } from '../../features/trainer/hooks';
import { sharedApi } from '../../features/shared/api';
import { BOARD_THEMES, PIECE_SETS } from '../../lib/boardThemes';
import { useAuth } from '../../store/authStore';
import { setBoardPrefs } from '../../store/preferencesStore';

const LANGUAGE_NAMES = {
  en: 'English',
  hi: 'हिन्दी (Hindi)',
  ta: 'தமிழ் (Tamil)',
  te: 'తెలుగు (Telugu)',
  kn: 'ಕನ್ನಡ (Kannada)',
  ml: 'മലയാളം (Malayalam)',
  fr: 'Français',
  es: 'Español',
  de: 'Deutsch',
};

const NOTIFICATION_LABELS = {
  sessions: ['Classes', 'Scheduled, rescheduled and cancelled classes'],
  assignments: ['Assignments', 'New assignments, submissions and grading'],
  feedback: ['Feedback', 'Feedback you receive and replies to yours'],
  content: ['Articles and gallery', 'New posts from the academy'],
  email: ['Also by email', 'Send a copy of each notification by email'],
};

const PREVIEW_FEN = 'r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3';

export default function SettingsPage() {
  const result = useLoader(() => sharedApi.settings(), []);
  return (
    <TrainerPage>
      <PageHeader title="Settings" subtitle="Your account, notifications and board" />
      <Loaded result={result}>
        {(settings) => <SettingsForms settings={settings} onSaved={result.reload} />}
      </Loaded>
    </TrainerPage>
  );
}

function SettingsForms({ settings, onSaved }) {
  const { refreshUser } = useAuth();
  const [profile, setProfile] = useState({
    full_name: settings.full_name,
    phone: settings.phone ?? '',
    language: settings.language,
  });
  const [notifications, setNotifications] = useState(settings.notifications);
  const [board, setBoard] = useState(settings.board);
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(null);

  async function save(section, body) {
    setSaving(section);
    setErrors({});
    try {
      const saved = await sharedApi.updateSettings(body);
      setBoardPrefs(saved.board);
      toast.success('Settings saved.');
      if (section === 'profile') await refreshUser();
      onSaved();
    } catch (error) {
      setErrors(fieldErrors(error));
      toast.error(errorMessage(error));
    } finally {
      setSaving(null);
    }
  }

  return (
    <div className="tr-stack">
      <Section title="Profile">
        <p className="tr-muted">
          Signed in as {settings.email} ({settings.role}). Your email and role are managed by the
          academy.
        </p>
        <form
          className="tr-form"
          onSubmit={(event) => {
            event.preventDefault();
            save('profile', { ...profile, phone: profile.phone.trim() || null });
          }}
        >
          <TextField
            label="Full name"
            required
            value={profile.full_name}
            onChange={(value) => setProfile({ ...profile, full_name: value })}
            error={errors.full_name}
          />
          <TextField
            label="Phone"
            value={profile.phone}
            onChange={(value) => setProfile({ ...profile, phone: value })}
            error={errors.phone}
          />
          <SelectField
            label="Language"
            value={profile.language}
            onChange={(value) => setProfile({ ...profile, language: value })}
            options={settings.options.languages.map((code) => ({
              value: code,
              label: LANGUAGE_NAMES[code] ?? code,
            }))}
            hint="Used for emails and, as translations are added, the interface."
          />
          <div>
            <Button type="submit" disabled={saving === 'profile'}>
              {saving === 'profile' ? 'Saving…' : 'Save profile'}
            </Button>
          </div>
        </form>
      </Section>

      <Section title="Notifications">
        <form
          className="tr-form"
          onSubmit={(event) => {
            event.preventDefault();
            save('notifications', { notifications });
          }}
        >
          {Object.entries(NOTIFICATION_LABELS).map(([key, [label, hint]]) => (
            <label key={key} className="tr-checkbox">
              <input
                type="checkbox"
                checked={notifications[key]}
                onChange={(event) =>
                  setNotifications({ ...notifications, [key]: event.target.checked })
                }
              />
              <span>
                <strong>{label}</strong> <span className="tr-muted">— {hint}</span>
              </span>
            </label>
          ))}
          <div>
            <Button type="submit" disabled={saving === 'notifications'}>
              {saving === 'notifications' ? 'Saving…' : 'Save notifications'}
            </Button>
          </div>
        </form>
      </Section>

      <Section title="Board">
        <div className="settings-board">
          <form
            className="tr-form"
            onSubmit={(event) => {
              event.preventDefault();
              save('board', { board });
            }}
          >
            <SelectField
              label="Board theme"
              value={board.theme}
              onChange={(value) => {
                setBoard({ ...board, theme: value });
              }}
              options={settings.options.board_themes.map((value) => ({
                value,
                label: BOARD_THEMES[value]?.label ?? value,
              }))}
            />
            <SelectField
              label="Piece set"
              value={board.pieces}
              onChange={(value) => {
                setBoard({ ...board, pieces: value });
              }}
              options={settings.options.piece_sets.map((value) => ({
                value,
                label: PIECE_SETS[value] ?? value,
              }))}
            />
            <label className="tr-checkbox">
              <input
                type="checkbox"
                checked={board.show_coordinates}
                onChange={(event) => {
                  setBoard({ ...board, show_coordinates: event.target.checked });
                }}
              />
              <span>Show coordinates</span>
            </label>
            <div>
              <Button type="submit" disabled={saving === 'board'}>
                {saving === 'board' ? 'Saving…' : 'Save board'}
              </Button>
            </div>
          </form>
          <div className="settings-board__preview" aria-label="Preview">
            <ChessBoard fen={PREVIEW_FEN} prefs={board} label="Board preview" />
          </div>
        </div>
      </Section>

      <PasswordSection />
    </div>
  );
}

function PasswordSection() {
  const empty = { current_password: '', new_password: '', confirm: '' };
  const [form, setForm] = useState(empty);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    if (form.new_password !== form.confirm) {
      setError('The new passwords do not match.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await sharedApi.changePassword({
        current_password: form.current_password,
        new_password: form.new_password,
      });
      setForm(empty);
      toast.success('Password changed. Other devices have been signed out.');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section title="Password">
      <form className="tr-form" onSubmit={submit}>
        <TextField
          label="Current password"
          type="password"
          autoComplete="current-password"
          required
          value={form.current_password}
          onChange={(value) => setForm({ ...form, current_password: value })}
        />
        <TextField
          label="New password"
          type="password"
          autoComplete="new-password"
          required
          hint="At least 8 characters, with a letter and a digit."
          value={form.new_password}
          onChange={(value) => setForm({ ...form, new_password: value })}
        />
        <TextField
          label="Confirm new password"
          type="password"
          autoComplete="new-password"
          required
          value={form.confirm}
          onChange={(value) => setForm({ ...form, confirm: value })}
        />
        {error && (
          <p className="tr-field__error" role="alert">
            {error}
          </p>
        )}
        <div>
          <Button type="submit" disabled={busy}>
            {busy ? 'Changing…' : 'Change password'}
          </Button>
        </div>
      </form>
    </Section>
  );
}
