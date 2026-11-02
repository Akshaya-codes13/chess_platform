import { useState } from 'react';
import { navigate, useRoute } from '../../routes/router';
import { errorMessage, fieldErrors, trainerApi } from '../../features/trainer/api';
import { fromLocalInput, localTimezone, toLocalInput } from '../../features/trainer/format';
import { useLoader } from '../../features/trainer/hooks';
import TrainerPage from '../../features/trainer/components/TrainerPage';
import { SelectField, TextArea, TextField } from '../../features/trainer/components/Field';
import { toast } from '../../features/trainer/components/toastStore';
import {
  Button,
  ButtonLink,
  Empty,
  Loaded,
  PageHeader,
  Section,
} from '../../features/trainer/components/ui';

export default function SessionFormPage() {
  const { params, query } = useRoute();
  const editing = Boolean(params.sessionId);
  const groups = useLoader(() => trainerApi.groups({ page_size: 100, is_active: true }), []);
  const existing = useLoader(
    () => (editing ? trainerApi.session(params.sessionId) : Promise.resolve(null)),
    [params.sessionId],
  );
  const ready = {
    ...groups,
    data: groups.data && (!editing || existing.data) ? groups.data : null,
    error: groups.error || existing.error,
  };

  return (
    <TrainerPage>
      <PageHeader
        back={
          editing
            ? { to: `/trainer/sessions/${params.sessionId}`, label: 'Session' }
            : { to: '/trainer/sessions', label: 'Sessions' }
        }
        title={editing ? 'Edit session' : 'Schedule a session'}
        subtitle={`Times use your timezone (${localTimezone}) and are stored in UTC.`}
      />
      <Loaded result={ready}>
        {(groupPage) =>
          existing.data && !existing.data.can_edit ? (
            <Empty
              title="This session can no longer be edited"
              message="Only upcoming scheduled sessions can be changed."
              action={
                <ButtonLink to={`/trainer/sessions/${existing.data.id}`} size="sm">
                  Back to session
                </ButtonLink>
              }
            />
          ) : groupPage.items.length ? (
            <SessionForm
              groups={groupPage.items}
              session={existing.data}
              initialGroup={query.group}
            />
          ) : (
            <Empty
              title="No active groups"
              message="You need an active assigned group to schedule sessions."
            />
          )
        }
      </Loaded>
    </TrainerPage>
  );
}

function defaultStart() {
  const date = new Date(Date.now() + 86400000);
  date.setMinutes(0, 0, 0);
  date.setHours(17);
  return date.toISOString();
}

function SessionForm({ groups, session, initialGroup }) {
  const [form, setForm] = useState(() => {
    const start = session?.start_time ?? defaultStart();
    const end = session?.end_time ?? new Date(new Date(start).getTime() + 3600000).toISOString();
    return {
      group_id:
        session?.group?.id ??
        (groups.some((g) => g.id === initialGroup) ? initialGroup : groups[0].id),
      title: session?.title ?? '',
      description: session?.description ?? '',
      learning_objective: session?.learning_objective ?? '',
      start_time: toLocalInput(start),
      end_time: toLocalInput(end),
      meeting_url: session?.meeting_url ?? '',
    };
  });
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);

  const set = (name) => (value) => {
    setForm((current) => ({ ...current, [name]: value }));
    setErrors((current) => ({ ...current, [name]: undefined, form: undefined }));
  };

  async function submit(event) {
    event.preventDefault();
    const next = {};
    if (form.title.trim().length < 3) next.title = 'Title must be at least 3 characters.';
    if (!form.start_time) next.start_time = 'Choose a start time.';
    if (!form.end_time) next.end_time = 'Choose an end time.';
    if (form.start_time && form.end_time && new Date(form.end_time) <= new Date(form.start_time))
      next.end_time = 'End time must be after start time.';
    if (form.start_time && new Date(form.start_time) <= new Date())
      next.start_time = 'Sessions must be scheduled in the future.';
    if (form.meeting_url && !/^https?:\/\//.test(form.meeting_url.trim()))
      next.meeting_url = 'Use a full http:// or https:// link.';
    if (Object.keys(next).length) {
      setErrors(next);
      return;
    }

    const body = {
      title: form.title.trim(),
      description: form.description.trim() || null,
      learning_objective: form.learning_objective.trim() || null,
      start_time: fromLocalInput(form.start_time),
      end_time: fromLocalInput(form.end_time),
      meeting_url: form.meeting_url.trim() || null,
    };

    setSaving(true);
    try {
      const saved = session
        ? await trainerApi.updateSession(session.id, body)
        : await trainerApi.createSession({ ...body, group_id: form.group_id });
      toast.success(session ? 'Session updated.' : 'Session scheduled.');
      navigate(`/trainer/sessions/${saved.id}`);
    } catch (error) {
      setErrors({ ...fieldErrors(error), form: errorMessage(error) });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Section>
      <form className="tr-form" onSubmit={submit} noValidate>
        {errors.form && (
          <p className="tr-callout tr-callout--error" role="alert">
            {errors.form}
          </p>
        )}
        <SelectField
          label="Group"
          required
          value={form.group_id}
          onChange={set('group_id')}
          error={errors.group_id}
          disabled={Boolean(session)}
          hint={session ? 'The group of a scheduled session cannot change.' : undefined}
          options={groups.map((group) => ({
            value: group.id,
            label: `${group.name} (${group.student_count} students)`,
          }))}
        />
        <TextField
          label="Title"
          required
          value={form.title}
          onChange={set('title')}
          error={errors.title}
          maxLength={150}
        />
        <TextField
          label="Learning objective"
          value={form.learning_objective}
          onChange={set('learning_objective')}
          error={errors.learning_objective}
          placeholder="e.g. Convert a Lucena position"
        />
        <TextArea
          label="Description"
          value={form.description}
          onChange={set('description')}
          error={errors.description}
        />
        <div className="tr-form-grid">
          <TextField
            label="Starts"
            type="datetime-local"
            required
            value={form.start_time}
            onChange={set('start_time')}
            error={errors.start_time}
          />
          <TextField
            label="Ends"
            type="datetime-local"
            required
            value={form.end_time}
            onChange={set('end_time')}
            error={errors.end_time}
            hint="Up to 8 hours."
          />
        </div>
        <TextField
          label="Meeting link"
          type="url"
          value={form.meeting_url}
          onChange={set('meeting_url')}
          error={errors.meeting_url}
          placeholder="https://"
          hint="Optional, for online sessions."
        />
        <div className="tr-form-actions">
          <Button
            variant="ghost"
            onClick={() =>
              navigate(session ? `/trainer/sessions/${session.id}` : '/trainer/sessions')
            }
          >
            Cancel
          </Button>
          <Button type="submit" disabled={saving}>
            {saving ? 'Saving…' : session ? 'Save changes' : 'Schedule session'}
          </Button>
        </div>
      </form>
    </Section>
  );
}
