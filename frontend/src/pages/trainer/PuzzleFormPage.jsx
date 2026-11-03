import { useEffect, useState } from 'react';
import { navigate, useRoute } from '../../routes/router';
import { errorMessage, fieldErrors, trainerApi } from '../../features/trainer/api';
import { DIFFICULTIES, titleCase } from '../../features/trainer/format';
import { useDebounced, useLoader } from '../../features/trainer/hooks';
import TrainerPage from '../../features/trainer/components/TrainerPage';
import FenBoard from '../../features/trainer/components/FenBoard';
import { SelectField, TextArea, TextField } from '../../features/trainer/components/Field';
import { toast } from '../../features/trainer/components/toastStore';
import { Button, Loaded, PageHeader, Section } from '../../features/trainer/components/ui';

const EMPTY = {
  fen: '',
  solution: '',
  rating: '',
  difficulty: '',
  type: 'puzzle',
  category_id: '',
  theme_ids: [],
  explanation: '',
};

export default function PuzzleFormPage() {
  // `?fen=` prefills a new puzzle, e.g. from the board editor.
  const { params, query } = useRoute();
  const editing = Boolean(params.puzzleId);
  const taxonomy = useLoader(() => trainerApi.taxonomy(), []);
  const existing = useLoader(
    () => (editing ? trainerApi.puzzle(params.puzzleId) : Promise.resolve(null)),
    [params.puzzleId],
  );
  const ready = {
    ...taxonomy,
    data: taxonomy.data && (!editing || existing.data) ? taxonomy.data : null,
    error: taxonomy.error || existing.error,
  };

  return (
    <TrainerPage>
      <PageHeader
        back={
          editing
            ? { to: `/trainer/puzzles/${params.puzzleId}`, label: 'Puzzle' }
            : { to: '/trainer/puzzles', label: 'Puzzle library' }
        }
        title={editing ? 'Edit puzzle' : 'Create puzzle'}
        subtitle="Enter the starting position as FEN and the full solution as UCI moves (e.g. e2e4 e7e5)."
      />
      <Loaded result={ready}>
        {(tax) => <PuzzleForm taxonomy={tax} puzzle={existing.data} initialFen={query.fen} />}
      </Loaded>
    </TrainerPage>
  );
}

function PuzzleForm({ taxonomy, puzzle, initialFen }) {
  const [form, setForm] = useState(() =>
    puzzle
      ? {
          fen: puzzle.fen,
          solution: puzzle.solution,
          rating: puzzle.rating ?? '',
          difficulty: puzzle.difficulty ?? '',
          type: puzzle.type,
          category_id: puzzle.category?.id ?? '',
          theme_ids: puzzle.themes.map((theme) => theme.id),
          explanation: puzzle.explanation ?? '',
        }
      : { ...EMPTY, fen: initialFen ?? '' },
  );
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [lastCheck, setLastCheck] = useState(null);
  const locked = Boolean(puzzle?.solution_locked);

  const set = (name) => (value) => {
    setForm((current) => ({ ...current, [name]: value }));
    setErrors((current) => ({ ...current, [name]: undefined, form: undefined }));
  };

  // Live validation by the server, so the editor uses the same rules as saving.
  const fen = useDebounced(form.fen, 500);
  const solution = useDebounced(form.solution, 500);
  const hasInput = Boolean(fen.trim() && solution.trim());
  useEffect(() => {
    if (!hasInput) return undefined;
    let cancelled = false;
    trainerApi
      .validatePuzzle({ fen, solution })
      .then((result) => !cancelled && setLastCheck({ fen, solution, result }))
      .catch(() => !cancelled && setLastCheck(null));
    return () => {
      cancelled = true;
    };
  }, [fen, solution, hasInput]);
  // Only show a result that belongs to the current (debounced) input.
  const check =
    hasInput && lastCheck?.fen === fen && lastCheck?.solution === solution
      ? lastCheck.result
      : null;

  function toggleTheme(id) {
    set('theme_ids')(
      form.theme_ids.includes(id)
        ? form.theme_ids.filter((t) => t !== id)
        : [...form.theme_ids, id],
    );
  }

  async function submit(event) {
    event.preventDefault();
    const nextErrors = {};
    if (!form.fen.trim()) nextErrors.fen = 'Enter a FEN.';
    if (!form.solution.trim()) nextErrors.solution = 'Enter the solution moves.';
    if (form.rating !== '' && (Number(form.rating) < 0 || Number(form.rating) > 4000))
      nextErrors.rating = 'Rating must be between 0 and 4000.';
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      return;
    }

    const body = {
      rating: form.rating === '' ? null : Number(form.rating),
      difficulty: form.difficulty || null,
      type: form.type,
      category_id: form.category_id || null,
      theme_ids: form.theme_ids,
      explanation: form.explanation.trim() || null,
    };
    if (!locked) Object.assign(body, { fen: form.fen.trim(), solution: form.solution.trim() });

    setSaving(true);
    try {
      const saved = puzzle
        ? await trainerApi.updatePuzzle(puzzle.id, body)
        : await trainerApi.createPuzzle(body);
      toast.success(
        puzzle
          ? 'Puzzle saved.'
          : 'Puzzle created as a draft. Publish it to use it in assignments.',
      );
      navigate(`/trainer/puzzles/${saved.id}`);
    } catch (error) {
      setErrors({ ...fieldErrors(error), form: errorMessage(error) });
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="tr-split" onSubmit={submit} noValidate>
      <Section title="Position and solution">
        <div className="tr-form">
          {errors.form && (
            <p className="tr-callout tr-callout--error" role="alert">
              {errors.form}
            </p>
          )}
          <TextField
            label="FEN"
            required
            value={form.fen}
            onChange={set('fen')}
            error={errors.fen}
            className="tr-input tr-input--mono"
            disabled={locked}
            spellCheck={false}
            placeholder="7k/8/5KQ1/8/8/8/8/8 w - - 0 1"
            hint={
              locked
                ? 'Locked: this puzzle is used in assignments or has attempts.'
                : 'All six FEN fields are required.'
            }
          />
          <TextField
            label="Solution (UCI moves)"
            required
            value={form.solution}
            onChange={set('solution')}
            error={errors.solution}
            className="tr-input tr-input--mono"
            disabled={locked}
            spellCheck={false}
            placeholder="g6g7"
            hint="Space-separated, starting with the side to move. Every move is checked for legality."
          />
          <ValidationResult check={check} />
          <div className="tr-form-grid">
            <TextField
              label="Rating"
              type="number"
              min="0"
              max="4000"
              value={form.rating}
              onChange={set('rating')}
              error={errors.rating}
            />
            <SelectField
              label="Difficulty"
              value={form.difficulty}
              onChange={set('difficulty')}
              options={DIFFICULTIES}
              placeholder="Not set"
              error={errors.difficulty}
            />
            <SelectField
              label="Type"
              value={form.type}
              onChange={set('type')}
              error={errors.type}
              options={['puzzle', 'study', 'composition'].map((value) => ({
                value,
                label: titleCase(value),
              }))}
            />
            <SelectField
              label="Category"
              value={form.category_id}
              onChange={set('category_id')}
              placeholder="None"
              error={errors.category_id}
              options={taxonomy.categories.map((category) => ({
                value: category.id,
                label: category.name,
              }))}
            />
          </div>
          <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
            <legend className="tr-field__label">Themes</legend>
            <div className="tr-chip-select" style={{ marginTop: 6 }}>
              {taxonomy.themes.map((theme) => (
                <label key={theme.id}>
                  <input
                    type="checkbox"
                    checked={form.theme_ids.includes(theme.id)}
                    onChange={() => toggleTheme(theme.id)}
                  />
                  <span>{theme.name}</span>
                </label>
              ))}
            </div>
            {errors.theme_ids && <p className="tr-field__error">{errors.theme_ids}</p>}
          </fieldset>
          <TextArea
            label="Explanation"
            value={form.explanation}
            onChange={set('explanation')}
            rows={4}
            error={errors.explanation}
            hint="Shown to students after they solve the puzzle."
          />
          <div className="tr-form-actions">
            <Button
              variant="ghost"
              onClick={() =>
                navigate(puzzle ? `/trainer/puzzles/${puzzle.id}` : '/trainer/puzzles')
              }
            >
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? 'Saving…' : puzzle ? 'Save changes' : 'Create draft'}
            </Button>
          </div>
        </div>
      </Section>
      <Section title="Preview">
        <FenBoard
          fen={check?.fen || form.fen}
          size="md"
          flipped={(check?.side_to_move || '') === 'black'}
        />
        {check?.valid && (
          <p className="tr-muted">
            {titleCase(check.side_to_move)} to move · {check.move_count} half-move
            {check.move_count === 1 ? '' : 's'}
            {check.ends_in_checkmate && ' · ends in checkmate'}
          </p>
        )}
      </Section>
    </form>
  );
}

function ValidationResult({ check }) {
  if (!check) return null;
  return check.valid ? (
    <p className="tr-callout tr-callout--success" role="status">
      ✓ Valid position and legal solution.
    </p>
  ) : (
    <p className="tr-callout tr-callout--error" role="status">
      {check.error}
    </p>
  );
}
