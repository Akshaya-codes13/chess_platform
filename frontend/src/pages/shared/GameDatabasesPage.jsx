import { useState } from 'react';
import { errorMessage } from '../../features/trainer/api';
import { TextArea, TextField } from '../../features/trainer/components/Field';
import TrainerPage from '../../features/trainer/components/TrainerPage';
import { toast } from '../../features/trainer/components/toastStore';
import {
  Button,
  ButtonLink,
  Empty,
  Loaded,
  PageHeader,
  Section,
} from '../../features/trainer/components/ui';
import { useLoader } from '../../features/trainer/hooks';
import { sharedApi } from '../../features/shared/api';
import { Link } from '../../routes/router';
import { usePortalBase, useRole } from './base';

export default function GameDatabasesPage() {
  const base = usePortalBase();
  const role = useRole();
  const result = useLoader(() => sharedApi.gameDatabases(), []);
  const [creating, setCreating] = useState(false);

  return (
    <TrainerPage>
      <PageHeader
        title="Game database"
        subtitle="Upload PGN games, organise them in folders, replay and analyse them."
        actions={
          <>
            <ButtonLink to={`${base}/board-editor`} variant="secondary">
              Board editor
            </ButtonLink>
            <Button onClick={() => setCreating((open) => !open)}>New database</Button>
          </>
        }
      />

      {creating && (
        <CreateDatabase
          canShare={role !== 'student'}
          onCreated={() => {
            setCreating(false);
            result.reload();
          }}
        />
      )}

      <Loaded result={result}>
        {(databases) =>
          databases.length === 0 ? (
            <Empty
              title="No game databases yet"
              message="Create a database, then upload a PGN file to start."
            />
          ) : (
            <div className="tr-grid tr-grid--cards">
              {databases.map((database) => (
                <Link
                  key={database.id}
                  to={`${base}/games/db/${database.id}`}
                  className="tr-card game-db-card"
                >
                  <strong>{database.name}</strong>
                  <span className="tr-muted">
                    {database.game_count} {database.game_count === 1 ? 'game' : 'games'} ·{' '}
                    {database.can_edit ? 'yours' : `by ${database.owner_name}`}
                    {database.is_shared ? ' · shared' : ''}
                  </span>
                  {database.description && <span>{database.description}</span>}
                </Link>
              ))}
            </div>
          )
        }
      </Loaded>
    </TrainerPage>
  );
}

function CreateDatabase({ canShare, onCreated }) {
  const [form, setForm] = useState({ name: '', description: '', is_shared: false });
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    try {
      await sharedApi.createGameDatabase({
        name: form.name.trim(),
        description: form.description.trim() || null,
        is_shared: form.is_shared,
      });
      toast.success('Database created.');
      onCreated();
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section title="New database">
      <form className="tr-form" onSubmit={submit}>
        <TextField
          label="Name"
          required
          maxLength={150}
          value={form.name}
          onChange={(name) => setForm({ ...form, name })}
        />
        <TextArea
          label="Description"
          value={form.description}
          onChange={(description) => setForm({ ...form, description })}
        />
        {canShare && (
          <label className="tr-checkbox">
            <input
              type="checkbox"
              checked={form.is_shared}
              onChange={(event) => setForm({ ...form, is_shared: event.target.checked })}
            />
            <span>Share with everyone in the academy (read-only for others)</span>
          </label>
        )}
        <div>
          <Button type="submit" disabled={busy || !form.name.trim()}>
            {busy ? 'Creating…' : 'Create database'}
          </Button>
        </div>
      </form>
    </Section>
  );
}
