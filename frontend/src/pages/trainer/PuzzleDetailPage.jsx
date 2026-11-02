import { useState } from 'react';
import { useRoute } from '../../routes/router';
import { errorMessage, trainerApi } from '../../features/trainer/api';
import { formatDateTime, titleCase } from '../../features/trainer/format';
import { useLoader } from '../../features/trainer/hooks';
import TrainerPage from '../../features/trainer/components/TrainerPage';
import FenBoard from '../../features/trainer/components/FenBoard';
import ConfirmDialog from '../../features/trainer/components/ConfirmDialog';
import { toast } from '../../features/trainer/components/toastStore';
import {
  Button,
  ButtonLink,
  Loaded,
  PageHeader,
  Section,
  Status,
} from '../../features/trainer/components/ui';

// action -> [allowed statuses, button label, confirmation text, tone]
const ACTIONS = {
  publish: [
    ['draft', 'archived'],
    'Publish',
    'Published puzzles are visible to all trainers and can be used in assignments.',
    'primary',
  ],
  unpublish: [
    ['published'],
    'Unpublish',
    'The puzzle returns to draft and can no longer be added to new assignments. Existing assignments keep it.',
    'secondary',
  ],
  archive: [
    ['draft', 'published'],
    'Archive',
    'Archived puzzles are hidden from other trainers and cannot be edited until restored.',
    'danger',
  ],
  restore: [['archived'], 'Restore', 'The puzzle returns to draft.', 'secondary'],
};
const DONE = {
  publish: 'published',
  unpublish: 'unpublished',
  archive: 'archived',
  restore: 'restored',
};

export default function PuzzleDetailPage() {
  const { params } = useRoute();
  const result = useLoader(() => trainerApi.puzzle(params.puzzleId), [params.puzzleId]);
  const [pending, setPending] = useState(null);
  const [busy, setBusy] = useState(false);

  async function runAction() {
    setBusy(true);
    try {
      await trainerApi.puzzleAction(params.puzzleId, pending);
      toast.success(`Puzzle ${DONE[pending]}.`);
      result.reload();
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(false);
      setPending(null);
    }
  }

  return (
    <TrainerPage>
      <Loaded result={result}>
        {(puzzle) => (
          <>
            <PageHeader
              back={{ to: '/trainer/puzzles', label: 'Puzzle library' }}
              title={puzzle.rating ? `Puzzle · rating ${puzzle.rating}` : 'Puzzle'}
              subtitle={`${titleCase(puzzle.side_to_move)} to move · ${puzzle.is_owner ? 'created by you' : `source: ${puzzle.source}`}`}
              actions={
                puzzle.is_owner && (
                  <>
                    {Object.entries(ACTIONS)
                      .filter(([, [allowed]]) => allowed.includes(puzzle.status))
                      .map(([action, [, label, , tone]]) => (
                        <Button
                          key={action}
                          variant={tone === 'danger' ? 'ghost' : tone}
                          onClick={() => setPending(action)}
                        >
                          {label}
                        </Button>
                      ))}
                    {puzzle.status !== 'archived' && (
                      <ButtonLink to={`/trainer/puzzles/${puzzle.id}/edit`}>Edit</ButtonLink>
                    )}
                  </>
                )
              }
            />
            <div className="tr-split">
              <Section>
                <FenBoard fen={puzzle.fen} size="lg" flipped={puzzle.side_to_move === 'black'} />
              </Section>
              <Section title="Details">
                <dl className="tr-stack" style={{ margin: 0 }}>
                  <Detail label="Status">
                    <Status value={puzzle.status} />
                  </Detail>
                  <Detail label="Solution (UCI)">
                    <span className="tr-code">{puzzle.solution}</span>
                  </Detail>
                  <Detail label="FEN">
                    <span className="tr-code">{puzzle.fen}</span>
                  </Detail>
                  <Detail label="Difficulty">{titleCase(puzzle.difficulty) || '—'}</Detail>
                  <Detail label="Type">{titleCase(puzzle.type)}</Detail>
                  <Detail label="Category">{puzzle.category?.name || '—'}</Detail>
                  <Detail label="Themes">
                    {puzzle.themes.length ? (
                      <span className="tr-tags">
                        {puzzle.themes.map((theme) => (
                          <span key={theme.id} className="tr-tag">
                            {theme.name}
                          </span>
                        ))}
                      </span>
                    ) : (
                      '—'
                    )}
                  </Detail>
                  <Detail label="Usage">
                    {puzzle.assignment_count} assignments · {puzzle.attempt_count} attempts
                  </Detail>
                  <Detail label="Updated">{formatDateTime(puzzle.updated_at)}</Detail>
                  {puzzle.explanation && <Detail label="Explanation">{puzzle.explanation}</Detail>}
                </dl>
                {puzzle.is_owner && puzzle.solution_locked && (
                  <p className="tr-callout tr-callout--info" style={{ marginBottom: 0 }}>
                    The position and solution are locked because this puzzle is used in assignments
                    or has attempts. Other details can still be edited.
                  </p>
                )}
                {!puzzle.is_owner && (
                  <p className="tr-callout tr-callout--info" style={{ marginBottom: 0 }}>
                    This puzzle belongs to the academy library or another trainer, so it is
                    read-only for you. You can still use it in assignments.
                  </p>
                )}
              </Section>
            </div>
            <ConfirmDialog
              open={Boolean(pending)}
              title={pending ? `${ACTIONS[pending][1]} this puzzle?` : ''}
              message={pending ? ACTIONS[pending][2] : ''}
              confirmLabel={pending ? ACTIONS[pending][1] : ''}
              tone={pending ? ACTIONS[pending][3] : 'primary'}
              busy={busy}
              onConfirm={runAction}
              onCancel={() => setPending(null)}
            />
          </>
        )}
      </Loaded>
    </TrainerPage>
  );
}

function Detail({ label, children }) {
  return (
    <div>
      <dt className="tr-field__label">{label}</dt>
      <dd style={{ margin: '2px 0 0' }}>{children}</dd>
    </div>
  );
}
