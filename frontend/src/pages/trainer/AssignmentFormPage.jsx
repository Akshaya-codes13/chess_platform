import { useState } from 'react';
import { navigate, useRoute } from '../../routes/router';
import { errorMessage, fieldErrors, trainerApi } from '../../features/trainer/api';
import {
  DIFFICULTIES,
  fromLocalInput,
  localTimezone,
  sideToMove,
  titleCase,
  toLocalInput,
} from '../../features/trainer/format';
import { useDebounced, useListState, useLoader } from '../../features/trainer/hooks';
import TrainerPage from '../../features/trainer/components/TrainerPage';
import FenBoard from '../../features/trainer/components/FenBoard';
import ConfirmDialog from '../../features/trainer/components/ConfirmDialog';
import Pagination from '../../features/trainer/components/Pagination';
import {
  FilterSelect,
  SearchInput,
  SelectField,
  TextArea,
  TextField,
} from '../../features/trainer/components/Field';
import { toast } from '../../features/trainer/components/toastStore';
import {
  Button,
  ButtonLink,
  Empty,
  Loaded,
  Loading,
  PageHeader,
  Section,
} from '../../features/trainer/components/ui';

export default function AssignmentFormPage() {
  const { params, query } = useRoute();
  const editing = Boolean(params.assignmentId);
  const groups = useLoader(() => trainerApi.groups({ page_size: 100, is_active: true }), []);
  const existing = useLoader(
    () => (editing ? trainerApi.assignment(params.assignmentId) : Promise.resolve(null)),
    [params.assignmentId],
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
            ? { to: `/trainer/assignments/${params.assignmentId}`, label: 'Assignment' }
            : { to: '/trainer/assignments', label: 'Assignments' }
        }
        title={editing ? 'Edit draft assignment' : 'New assignment'}
      />
      <Loaded result={ready}>
        {(groupPage) =>
          existing.data && existing.data.status !== 'draft' ? (
            <Empty
              title="Only drafts can be edited"
              message="This assignment has already been published."
              action={
                <ButtonLink to={`/trainer/assignments/${existing.data.id}`} size="sm">
                  View progress
                </ButtonLink>
              }
            />
          ) : groupPage.items.length ? (
            <AssignmentForm
              groups={groupPage.items}
              assignment={existing.data}
              initialGroup={query.group}
            />
          ) : (
            <Empty
              title="No active groups"
              message="You need an active assigned group before creating assignments."
            />
          )
        }
      </Loaded>
    </TrainerPage>
  );
}

function AssignmentForm({ groups, assignment, initialGroup }) {
  const [form, setForm] = useState(() => ({
    title: assignment?.title ?? '',
    description: assignment?.description ?? '',
    group_id:
      assignment?.group?.id ??
      (groups.some((g) => g.id === initialGroup) ? initialGroup : groups[0].id),
    whole_group: assignment ? assignment.assignment_type === 'group' : true,
    student_ids:
      assignment?.assignment_type === 'individual'
        ? assignment.recipients.map((r) => r.student_id)
        : [],
    start_date: toLocalInput(assignment?.start_date),
    due_date: toLocalInput(assignment?.due_date),
  }));
  const [puzzles, setPuzzles] = useState(
    () =>
      assignment?.puzzles.map((p) => ({
        id: p.puzzle_id,
        fen: p.fen,
        rating: p.rating,
        difficulty: p.difficulty,
      })) ?? [],
  );
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [confirmPublish, setConfirmPublish] = useState(false);

  const students = useLoader(
    () => trainerApi.groupStudents(form.group_id, { page_size: 100 }),
    [form.group_id],
  );

  const set = (name) => (value) => {
    setForm((current) => ({ ...current, [name]: value }));
    setErrors((current) => ({ ...current, [name]: undefined, form: undefined }));
  };

  function changeGroup(groupId) {
    // Selected students belong to the previous group, so reset them.
    setForm((current) => ({ ...current, group_id: groupId, student_ids: [] }));
  }

  function toggleStudent(id) {
    set('student_ids')(
      form.student_ids.includes(id)
        ? form.student_ids.filter((s) => s !== id)
        : [...form.student_ids, id],
    );
  }

  function move(index, delta) {
    setPuzzles((current) => {
      const next = [...current];
      const [item] = next.splice(index, 1);
      next.splice(index + delta, 0, item);
      return next;
    });
  }

  function validate(publishing) {
    const next = {};
    if (form.title.trim().length < 3) next.title = 'Title must be at least 3 characters.';
    if (!form.whole_group && !form.student_ids.length)
      next.student_ids = 'Select at least one student, or assign the whole group.';
    if (form.start_date && form.due_date && new Date(form.due_date) < new Date(form.start_date)) {
      next.due_date = 'Due date cannot be earlier than the start date.';
    }
    if (publishing && !puzzles.length) next.puzzles = 'Add at least one puzzle before publishing.';
    if (publishing && form.due_date && new Date(form.due_date) <= new Date())
      next.due_date = 'The due date is in the past.';
    setErrors(next);
    return !Object.keys(next).length;
  }

  async function save(publishing) {
    setConfirmPublish(false);
    if (!validate(publishing)) return;

    const body = {
      title: form.title.trim(),
      description: form.description.trim() || null,
      group_id: form.group_id,
      puzzle_ids: puzzles.map((p) => p.id),
      student_ids: form.whole_group ? null : form.student_ids,
      start_date: fromLocalInput(form.start_date),
      due_date: fromLocalInput(form.due_date),
    };

    setSaving(true);
    try {
      let saved;
      if (assignment) {
        saved = await trainerApi.updateAssignment(assignment.id, body);
        if (publishing) saved = await trainerApi.assignmentAction(assignment.id, 'publish');
      } else {
        saved = await trainerApi.createAssignment({ ...body, publish: publishing });
      }
      toast.success(publishing ? 'Assignment published.' : 'Draft saved.');
      navigate(`/trainer/assignments/${saved.id}`);
    } catch (error) {
      setErrors({ ...fieldErrors(error), form: errorMessage(error) });
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      className="tr-stack"
      onSubmit={(event) => {
        event.preventDefault();
        save(false);
      }}
      noValidate
    >
      {errors.form && (
        <p className="tr-callout tr-callout--error" role="alert">
          {errors.form}
        </p>
      )}
      <div className="tr-split">
        <Section title="Details">
          <div className="tr-form">
            <TextField
              label="Title"
              required
              value={form.title}
              onChange={set('title')}
              error={errors.title}
              maxLength={150}
            />
            <TextArea
              label="Description"
              value={form.description}
              onChange={set('description')}
              error={errors.description}
              hint="What should students focus on?"
            />
            <div className="tr-form-grid">
              <TextField
                label="Start date"
                type="datetime-local"
                value={form.start_date}
                onChange={set('start_date')}
                error={errors.start_date}
                hint={`Your timezone: ${localTimezone}`}
              />
              <TextField
                label="Due date"
                type="datetime-local"
                value={form.due_date}
                onChange={set('due_date')}
                error={errors.due_date}
              />
            </div>
          </div>
        </Section>

        <Section title="Recipients">
          <div className="tr-form">
            <SelectField
              label="Group"
              required
              value={form.group_id}
              onChange={changeGroup}
              options={groups.map((g) => ({
                value: g.id,
                label: `${g.name} (${g.student_count})`,
              }))}
              error={errors.group_id}
            />
            <label className="tr-checkbox">
              <input
                type="checkbox"
                checked={form.whole_group}
                onChange={(event) => set('whole_group')(event.target.checked)}
              />
              Assign to the whole group
            </label>
            {form.whole_group ? (
              <p className="tr-muted" style={{ margin: 0 }}>
                Everyone in the group when the assignment is published will receive it.
              </p>
            ) : students.loading && !students.data ? (
              <Loading label="Loading students…" />
            ) : (
              <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
                <legend className="tr-field__label">
                  Students ({form.student_ids.length} selected)
                </legend>
                <div className="tr-chip-select" style={{ marginTop: 6 }}>
                  {students.data?.items.map((student) => (
                    <label key={student.student_id}>
                      <input
                        type="checkbox"
                        checked={form.student_ids.includes(student.student_id)}
                        onChange={() => toggleStudent(student.student_id)}
                      />
                      <span>{student.full_name}</span>
                    </label>
                  ))}
                </div>
                {!students.data?.items.length && (
                  <p className="tr-muted">This group has no students.</p>
                )}
                {errors.student_ids && <p className="tr-field__error">{errors.student_ids}</p>}
              </fieldset>
            )}
          </div>
        </Section>
      </div>

      <Section title={`Puzzles (${puzzles.length})`}>
        {errors.puzzles && <p className="tr-callout tr-callout--error">{errors.puzzles}</p>}
        {puzzles.length ? (
          <ol className="tr-list" style={{ marginBottom: 16 }}>
            {puzzles.map((puzzle, index) => (
              <li key={puzzle.id}>
                <span className="tr-row">
                  <strong>{index + 1}.</strong>
                  <FenBoard
                    fen={puzzle.fen}
                    size="sm"
                    flipped={sideToMove(puzzle.fen) === 'Black'}
                  />
                  <span className="tr-muted">
                    {puzzle.rating ? `Rating ${puzzle.rating}` : 'Unrated'} ·{' '}
                    {titleCase(puzzle.difficulty) || '—'} · {sideToMove(puzzle.fen)} to move
                  </span>
                </span>
                <span className="tr-row">
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={index === 0}
                    onClick={() => move(index, -1)}
                    aria-label={`Move puzzle ${index + 1} up`}
                  >
                    ↑
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={index === puzzles.length - 1}
                    onClick={() => move(index, 1)}
                    aria-label={`Move puzzle ${index + 1} down`}
                  >
                    ↓
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setPuzzles(puzzles.filter((p) => p.id !== puzzle.id))}
                    aria-label={`Remove puzzle ${index + 1}`}
                  >
                    Remove
                  </Button>
                </span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="tr-muted">
            No puzzles selected yet. Add published puzzles from the picker below.
          </p>
        )}
        <PuzzlePicker
          selected={puzzles.map((p) => p.id)}
          onAdd={(puzzle) => {
            setPuzzles((current) => [...current, puzzle]);
            setErrors((current) => ({ ...current, puzzles: undefined }));
          }}
        />
      </Section>

      <div className="tr-form-actions">
        <Button
          variant="ghost"
          onClick={() =>
            navigate(assignment ? `/trainer/assignments/${assignment.id}` : '/trainer/assignments')
          }
        >
          Cancel
        </Button>
        <Button type="submit" variant="secondary" disabled={saving}>
          {saving ? 'Saving…' : 'Save draft'}
        </Button>
        <Button disabled={saving} onClick={() => validate(true) && setConfirmPublish(true)}>
          Publish
        </Button>
      </div>

      <ConfirmDialog
        open={confirmPublish}
        title="Publish this assignment?"
        message="Students will see it immediately (or from the start date). Published assignments can no longer be edited, only closed or cancelled."
        confirmLabel="Publish"
        busy={saving}
        onConfirm={() => save(true)}
        onCancel={() => setConfirmPublish(false)}
      />
    </form>
  );
}

function PuzzlePicker({ selected, onAdd }) {
  const [filters, setFilter] = useListState({
    search: '',
    difficulty: null,
    status: 'published',
    page_size: 8,
  });
  const search = useDebounced(filters.search);
  const query = { ...filters, search };
  const result = useLoader(() => trainerApi.puzzles(query), [JSON.stringify(query)]);

  return (
    <div className="tr-card" style={{ background: 'transparent' }}>
      <h3 className="tr-card__title" style={{ marginBottom: 10 }}>
        Add puzzles
      </h3>
      <div className="tr-filters">
        <SearchInput
          label="Search puzzles"
          value={filters.search}
          onChange={(value) => setFilter('search', value)}
        />
        <FilterSelect
          label="Difficulty"
          value={filters.difficulty}
          onChange={(value) => setFilter('difficulty', value)}
          options={DIFFICULTIES}
        />
      </div>
      <Loaded result={result}>
        {(page) =>
          page.items.length ? (
            <>
              <ul className="tr-list">
                {page.items.map((puzzle) => (
                  <li key={puzzle.id}>
                    <span className="tr-row">
                      <FenBoard
                        fen={puzzle.fen}
                        size="sm"
                        flipped={sideToMove(puzzle.fen) === 'Black'}
                      />
                      <span>
                        <strong>{puzzle.rating ? `Rating ${puzzle.rating}` : 'Unrated'}</strong>
                        <br />
                        <span className="tr-muted">
                          {titleCase(puzzle.difficulty) || '—'} ·{' '}
                          {puzzle.themes.map((t) => t.name).join(', ') || 'no themes'}
                        </span>
                      </span>
                    </span>
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={selected.includes(puzzle.id)}
                      onClick={() =>
                        onAdd({
                          id: puzzle.id,
                          fen: puzzle.fen,
                          rating: puzzle.rating,
                          difficulty: puzzle.difficulty,
                        })
                      }
                    >
                      {selected.includes(puzzle.id) ? 'Added' : 'Add'}
                    </Button>
                  </li>
                ))}
              </ul>
              <Pagination
                page={page.page}
                pages={page.pages}
                total={page.total}
                label="published puzzles"
                onChange={(value) => setFilter('page', value)}
              />
            </>
          ) : (
            <Empty
              title="No published puzzles found"
              message="Publish your draft puzzles to use them here."
            />
          )
        }
      </Loaded>
    </div>
  );
}
