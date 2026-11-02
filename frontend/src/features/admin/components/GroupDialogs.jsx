import { useState } from 'react';
import { SearchInput, TextArea, TextField } from '../../trainer/components/Field';
import { useDebounced, useLoader } from '../../trainer/hooks';
import { adminApi } from '../api';
import { useSubmit } from '../hooks';
import { onlyErrors, validateName } from '../validation';
import FormDialog from './FormDialog';
import TrainerSelect from './TrainerSelect';

const PICKER_PAGE_SIZE = 25;

/** Create a group (when `group` is absent) or edit its details. */
export function GroupDialog({ open, group, onClose, onSaved }) {
  const initial = {
    name: group?.name ?? '',
    description: group?.description ?? '',
    trainer_user_id: '',
    is_active: group?.is_active ?? true,
  };
  const [values, setValues] = useState(initial);
  const [clientErrors, setClientErrors] = useState({});
  const submit = useSubmit();
  const errors = { ...submit.fields, ...clientErrors };
  const set = (name) => (value) => setValues((current) => ({ ...current, [name]: value }));

  function close() {
    setValues(initial);
    setClientErrors({});
    submit.reset();
    onClose();
  }

  async function handleSubmit() {
    const found = onlyErrors({
      name: validateName(values.name, 'Group name'),
      trainer_user_id: !group && !values.trainer_user_id ? 'Choose a trainer.' : null,
    });
    setClientErrors(found);
    if (Object.keys(found).length) return;

    const body = {
      name: values.name.trim(),
      description: values.description.trim() || null,
      is_active: values.is_active,
    };
    const saved = await submit.run(
      () =>
        group
          ? adminApi.updateGroup(group.id, body)
          : adminApi.createGroup({ ...body, trainer_user_id: values.trainer_user_id }),
      group ? 'Group updated.' : 'Group created.',
    );
    if (saved) {
      onSaved(saved);
      if (group) onClose();
      else close();
    }
  }

  return (
    <FormDialog
      open={open}
      title={group ? 'Edit group' : 'New group'}
      submitLabel={group ? 'Save' : 'Create group'}
      busy={submit.busy}
      error={submit.error}
      onSubmit={handleSubmit}
      onClose={close}
    >
      <TextField
        label="Group name"
        required
        value={values.name}
        onChange={set('name')}
        error={errors.name}
        maxLength={120}
      />
      <TextArea
        label="Description"
        value={values.description}
        onChange={set('description')}
        maxLength={5000}
      />
      {!group && (
        <TrainerSelect
          required
          value={values.trainer_user_id}
          onChange={set('trainer_user_id')}
          error={errors.trainer_user_id}
        />
      )}
      <label className="tr-checkbox">
        <input
          type="checkbox"
          checked={values.is_active}
          onChange={(event) => set('is_active')(event.target.checked)}
        />
        Active (trainers can schedule sessions and assignments for it)
      </label>
    </FormDialog>
  );
}

export function AssignTrainerDialog({ open, group, onClose, onSaved }) {
  const [trainerId, setTrainerId] = useState('');
  const [missing, setMissing] = useState(false);
  const submit = useSubmit();

  function close() {
    setTrainerId('');
    setMissing(false);
    submit.reset();
    onClose();
  }

  async function handleSubmit() {
    setMissing(!trainerId);
    if (!trainerId) return;
    const saved = await submit.run(
      () => adminApi.assignTrainer(group.id, trainerId),
      'Trainer assigned.',
    );
    if (saved) {
      onSaved(saved);
      close();
    }
  }

  return (
    <FormDialog
      open={open}
      title="Change trainer"
      submitLabel="Assign trainer"
      busy={submit.busy}
      error={submit.error}
      onSubmit={handleSubmit}
      onClose={close}
    >
      <p>
        {group.name} is run by <strong>{group.trainer.full_name}</strong>. Each group has exactly
        one trainer, so the new trainer replaces them.
      </p>
      <TrainerSelect
        label="New trainer"
        required
        value={trainerId}
        onChange={setTrainerId}
        error={missing ? 'Choose a trainer.' : submit.fields.trainer_user_id}
      />
    </FormDialog>
  );
}

/** Search students who are not yet members and add a selection in one batch. */
export function AddStudentsDialog({ open, group, onClose, onSaved }) {
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState({});
  const debounced = useDebounced(search);
  const submit = useSubmit();
  const result = useLoader(
    () =>
      open
        ? adminApi.students({
            search: debounced,
            exclude_group_id: group.id,
            page_size: PICKER_PAGE_SIZE,
          })
        : Promise.resolve(null),
    [open, debounced, group.id],
  );
  const candidates = result.data?.items ?? [];
  const selectedIds = Object.keys(selected);

  function close() {
    setSearch('');
    setSelected({});
    submit.reset();
    onClose();
  }

  function toggle(student) {
    setSelected((current) => {
      const next = { ...current };
      if (next[student.id]) delete next[student.id];
      else next[student.id] = student;
      return next;
    });
  }

  async function handleSubmit() {
    if (!selectedIds.length) return;
    const saved = await submit.run(
      () => adminApi.addStudents(group.id, selectedIds),
      `${selectedIds.length} student${selectedIds.length === 1 ? '' : 's'} added.`,
    );
    if (saved) {
      onSaved(saved);
      close();
    }
  }

  return (
    <FormDialog
      open={open}
      title={`Add students to ${group.name}`}
      submitLabel={selectedIds.length ? `Add ${selectedIds.length}` : 'Add students'}
      busy={submit.busy}
      error={submit.error}
      onSubmit={handleSubmit}
      onClose={close}
    >
      <SearchInput label="Find students by name or email" value={search} onChange={setSearch} />
      <fieldset className="ad-picker" aria-busy={result.loading}>
        <legend className="tr-visually-hidden">Students who are not members</legend>
        {result.error && <p className="tr-callout tr-callout--error">Could not load students.</p>}
        {!result.error && result.data && !candidates.length && (
          <p className="tr-muted">No students match, or all of them are already members.</p>
        )}
        {candidates.map((student) => {
          const unavailable = !student.trainer;
          return (
            <label key={student.id}>
              <input
                type="checkbox"
                checked={Boolean(selected[student.id])}
                disabled={unavailable}
                onChange={() => toggle(student)}
              />
              <span>
                {student.full_name} <span className="tr-muted">· {student.email}</span>
                {unavailable && <span className="tr-muted"> · needs a profile first</span>}
                {!student.is_active && <span className="tr-muted"> · inactive</span>}
              </span>
            </label>
          );
        })}
      </fieldset>
      {(result.data?.total ?? 0) > candidates.length && (
        <p className="tr-muted">
          Showing {candidates.length} of {result.data.total}. Search to narrow the list.
        </p>
      )}
      {selectedIds.length > 0 && (
        <p className="tr-muted">
          Selected:{' '}
          {Object.values(selected)
            .map((student) => student.full_name)
            .join(', ')}
        </p>
      )}
    </FormDialog>
  );
}
