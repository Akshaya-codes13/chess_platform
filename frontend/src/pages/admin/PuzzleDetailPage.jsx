import { useState } from 'react';
import { useRoute } from '../../routes/router';
import { adminApi } from '../../features/admin/api';
import AdminPage from '../../features/admin/components/AdminPage';
import { UserLink } from '../../features/admin/components/shared';
import { runAction } from '../../features/admin/utils';
import ConfirmDialog from '../../features/trainer/components/ConfirmDialog';
import FenBoard from '../../features/trainer/components/FenBoard';
import {
  Button,
  Loaded,
  PageHeader,
  Section,
  StatCard,
  Status,
} from '../../features/trainer/components/ui';
import { formatDate, titleCase } from '../../features/trainer/format';
import { useLoader } from '../../features/trainer/hooks';

const ACTIONS = {
  archive: {
    title: 'Archive this puzzle?',
    message:
      'Trainers will no longer find it in the library or add it to new assignments. Existing assignments and attempts are kept.',
    tone: 'danger',
    done: 'Puzzle archived.',
  },
  publish: {
    title: 'Publish this puzzle?',
    message: 'Every trainer will be able to use it. The position and solution are checked first.',
    tone: 'primary',
    done: 'Puzzle published.',
  },
};

export default function PuzzleDetailPage() {
  const { params } = useRoute();
  const result = useLoader(() => adminApi.puzzle(params.puzzleId), [params.puzzleId]);
  const [action, setAction] = useState(null);
  const [busy, setBusy] = useState(false);

  async function confirm() {
    setBusy(true);
    const saved = await runAction(
      () => adminApi.puzzleAction(params.puzzleId, action),
      ACTIONS[action].done,
    );
    setBusy(false);
    setAction(null);
    if (saved) result.reload();
  }

  return (
    <AdminPage>
      <Loaded result={result}>
        {(puzzle) => (
          <>
            <PageHeader
              back={{ to: '/admin/puzzles', label: 'Puzzles' }}
              title={puzzle.lichess_id ?? `Puzzle #${puzzle.id.slice(0, 8)}`}
              subtitle={<Status value={puzzle.status} />}
              actions={
                <>
                  {puzzle.status !== 'archived' && (
                    <Button variant="danger" onClick={() => setAction('archive')}>
                      Archive
                    </Button>
                  )}
                  {puzzle.status !== 'published' && (
                    <Button onClick={() => setAction('publish')}>Publish</Button>
                  )}
                </>
              }
            />
            {puzzle.issues.length > 0 && (
              <div className="tr-callout tr-callout--error" role="note">
                <strong>This record has problems:</strong>
                <ul className="ad-issues">
                  {puzzle.issues.map((issue) => (
                    <li key={issue}>{issue}</li>
                  ))}
                </ul>
              </div>
            )}
            <div className="tr-split">
              <Section title="Position">
                <FenBoard fen={puzzle.fen} />
                <p className="ad-fen">{puzzle.fen}</p>
              </Section>
              <Section title="Details">
                <dl className="ad-dl">
                  <dt>Solution (UCI)</dt>
                  <dd className="ad-fen">{puzzle.solution || '—'}</dd>
                  <dt>Rating</dt>
                  <dd>
                    {puzzle.rating ?? '—'}
                    {puzzle.rating_deviation !== null && ` ± ${puzzle.rating_deviation}`}
                  </dd>
                  <dt>Difficulty</dt>
                  <dd>{puzzle.difficulty ? titleCase(puzzle.difficulty) : '—'}</dd>
                  <dt>Type</dt>
                  <dd>{titleCase(puzzle.type)}</dd>
                  <dt>Source</dt>
                  <dd>{puzzle.source}</dd>
                  <dt>Author</dt>
                  <dd>
                    {puzzle.author ? (
                      <UserLink user={puzzle.author} role="trainer" />
                    ) : (
                      'Library puzzle'
                    )}
                  </dd>
                  <dt>Category</dt>
                  <dd>{puzzle.category?.name ?? '—'}</dd>
                  <dt>Themes</dt>
                  <dd>{puzzle.themes.map((t) => t.name).join(', ') || '—'}</dd>
                  <dt>Popularity</dt>
                  <dd>{puzzle.popularity ?? '—'}</dd>
                  <dt>Added</dt>
                  <dd>{formatDate(puzzle.created_at)}</dd>
                </dl>
                {puzzle.explanation && <p>{puzzle.explanation}</p>}
              </Section>
            </div>
            <div className="tr-grid tr-grid--stats">
              <StatCard label="Used in assignments" value={puzzle.usage.assignment_count} />
              <StatCard label="Attempts" value={puzzle.usage.attempt_count} />
              <StatCard label="Solved" value={puzzle.usage.solved_count} />
            </div>
            <ConfirmDialog
              open={Boolean(action)}
              title={action ? ACTIONS[action].title : ''}
              message={action ? ACTIONS[action].message : ''}
              confirmLabel={action ? titleCase(action) : ''}
              tone={action ? ACTIONS[action].tone : 'primary'}
              busy={busy}
              onConfirm={confirm}
              onCancel={() => setAction(null)}
            />
          </>
        )}
      </Loaded>
    </AdminPage>
  );
}
