import { useRef, useState } from 'react';
import { errorMessage } from '../../features/trainer/api';
import ConfirmDialog from '../../features/trainer/components/ConfirmDialog';
import DataTable from '../../features/trainer/components/DataTable';
import { SearchInput, TextArea, TextField } from '../../features/trainer/components/Field';
import Pagination from '../../features/trainer/components/Pagination';
import TrainerPage from '../../features/trainer/components/TrainerPage';
import { toast } from '../../features/trainer/components/toastStore';
import { Button, Empty, Loaded, PageHeader, Section } from '../../features/trainer/components/ui';
import { useDebounced, useLoader } from '../../features/trainer/hooks';
import { sharedApi } from '../../features/shared/api';
import { Link, navigate, useRoute } from '../../routes/router';
import { usePortalBase } from './base';

export default function GameBrowserPage() {
  const base = usePortalBase();
  const { params, query } = useRoute();
  const folderId = query.folder || null;
  const [search, setSearch] = useState('');
  const debounced = useDebounced(search.trim());
  const [page, setPage] = useState(1);
  const result = useLoader(
    () =>
      sharedApi.browse(params.databaseId, {
        folder_id: folderId,
        search: debounced || null,
        page,
        page_size: 25,
      }),
    [params.databaseId, folderId, debounced, page],
  );

  const folderPath = (id) => `${base}/games/db/${params.databaseId}${id ? `?folder=${id}` : ''}`;

  return (
    <TrainerPage>
      <Loaded result={result}>
        {(data) => (
          <>
            <PageHeader
              back={{ to: `${base}/games`, label: 'All databases' }}
              title={data.database.name}
              subtitle={`${data.database.game_count} games${data.database.is_shared ? ' · shared' : ''}${
                data.database.can_edit ? '' : ` · by ${data.database.owner_name}`
              }`}
            />

            <nav aria-label="Breadcrumb" className="breadcrumbs">
              <ol>
                {data.breadcrumbs.map((crumb, index) => {
                  const last = index === data.breadcrumbs.length - 1;
                  return (
                    <li key={crumb.id ?? 'root'}>
                      {last ? (
                        <span aria-current="page">{crumb.name}</span>
                      ) : (
                        <Link to={folderPath(crumb.id)}>{crumb.name}</Link>
                      )}
                    </li>
                  );
                })}
              </ol>
            </nav>

            {data.database.can_edit && (
              <Toolbar
                databaseId={data.database.id}
                folderId={folderId}
                onChanged={() => {
                  setPage(1);
                  result.reload();
                }}
              />
            )}

            <div className="tr-filters">
              <SearchInput
                value={search}
                onChange={(value) => {
                  setSearch(value);
                  setPage(1);
                }}
                label="Search players or event in this database"
              />
            </div>

            {!debounced && data.folders.length > 0 && (
              <Section title="Folders">
                <ul className="folder-list">
                  {data.folders.map((folder) => (
                    <li key={folder.id}>
                      <Link to={folderPath(folder.id)} className="folder-link">
                        <span aria-hidden="true">📁</span> {folder.name}
                        <span className="tr-muted"> · {folder.game_count}</span>
                      </Link>
                      {data.database.can_edit && (
                        <FolderActions folder={folder} onChanged={result.reload} />
                      )}
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            <Section title={debounced ? `Results for “${debounced}”` : 'Games'}>
              {data.games.items.length === 0 ? (
                <Empty
                  title={debounced ? 'No matching games' : 'No games here yet'}
                  message={data.database.can_edit ? 'Upload a PGN file to add games.' : undefined}
                />
              ) : (
                <>
                  <DataTable
                    caption="Games"
                    rows={data.games.items}
                    onRowClick={(game) => navigate(`${base}/games/view/${game.id}`)}
                    columns={[
                      {
                        key: 'players',
                        label: 'Players',
                        render: (game) => (
                          <Link to={`${base}/games/view/${game.id}`}>
                            {game.white}
                            {game.white_elo ? ` (${game.white_elo})` : ''} – {game.black}
                            {game.black_elo ? ` (${game.black_elo})` : ''}
                          </Link>
                        ),
                      },
                      { key: 'result', label: 'Result' },
                      { key: 'event', label: 'Event', render: (game) => game.event ?? '—' },
                      { key: 'game_date', label: 'Date', render: (game) => game.game_date ?? '—' },
                      { key: 'eco', label: 'ECO', render: (game) => game.eco ?? '—' },
                      {
                        key: 'ply_count',
                        label: 'Moves',
                        align: 'right',
                        render: (game) => Math.ceil(game.ply_count / 2),
                      },
                    ]}
                  />
                  <Pagination
                    page={data.games.page}
                    pages={data.games.pages}
                    total={data.games.total}
                    onChange={setPage}
                    label="games"
                  />
                </>
              )}
            </Section>
          </>
        )}
      </Loaded>
    </TrainerPage>
  );
}

function Toolbar({ databaseId, folderId, onChanged }) {
  const [mode, setMode] = useState(null);
  const [folderName, setFolderName] = useState('');
  const [pgnText, setPgnText] = useState('');
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState(null);
  const fileRef = useRef(null);

  async function createFolder(event) {
    event.preventDefault();
    setBusy(true);
    try {
      await sharedApi.createFolder(databaseId, { name: folderName.trim(), parent_id: folderId });
      setFolderName('');
      setMode(null);
      toast.success('Folder created.');
      onChanged();
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function upload(event) {
    event.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file && !pgnText.trim()) {
      toast.error('Choose a .pgn file or paste PGN text.');
      return;
    }
    const form = new FormData();
    if (file) form.append('file', file);
    else form.append('pgn', pgnText);
    if (folderId) form.append('folder_id', folderId);

    setBusy(true);
    setReport(null);
    try {
      const result = await sharedApi.importPgn(databaseId, form);
      setReport(result);
      setPgnText('');
      if (fileRef.current) fileRef.current.value = '';
      toast.success(`Imported ${result.imported} game${result.imported === 1 ? '' : 's'}.`);
      onChanged();
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section>
      <div className="tr-page-actions">
        <Button
          variant={mode === 'upload' ? 'primary' : 'secondary'}
          onClick={() => setMode(mode === 'upload' ? null : 'upload')}
        >
          Upload PGN
        </Button>
        <Button
          variant={mode === 'folder' ? 'primary' : 'secondary'}
          onClick={() => setMode(mode === 'folder' ? null : 'folder')}
        >
          New folder
        </Button>
      </div>

      {mode === 'folder' && (
        <form className="tr-form" onSubmit={createFolder}>
          <TextField
            label="Folder name"
            required
            maxLength={150}
            value={folderName}
            onChange={setFolderName}
          />
          <div>
            <Button type="submit" disabled={busy || !folderName.trim()}>
              Create folder
            </Button>
          </div>
        </form>
      )}

      {mode === 'upload' && (
        <form className="tr-form" onSubmit={upload}>
          <div className="tr-field">
            <label className="tr-field__label" htmlFor="pgn-file">
              PGN file (up to 2 MB, 500 games)
            </label>
            <input
              id="pgn-file"
              ref={fileRef}
              type="file"
              accept=".pgn,application/x-chess-pgn,text/plain"
            />
          </div>
          <TextArea
            label="…or paste PGN"
            rows={6}
            value={pgnText}
            onChange={setPgnText}
            placeholder={'[White "…"]\n[Black "…"]\n\n1. e4 e5 2. Nf3 …'}
          />
          <div>
            <Button type="submit" disabled={busy}>
              {busy ? 'Importing…' : 'Import games'}
            </Button>
          </div>
        </form>
      )}

      {report && report.skipped > 0 && (
        <div className="tr-callout tr-callout--warning" role="status">
          <strong>
            {report.imported} imported, {report.skipped} skipped.
          </strong>
          <ul>
            {report.errors.map((item) => (
              <li key={item.index}>
                Game {item.index}: {item.error}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Section>
  );
}

function FolderActions({ folder, onChanged }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  async function rename() {
    const name = window.prompt('Rename folder', folder.name);
    if (!name || name.trim() === folder.name) return;
    try {
      await sharedApi.renameFolder(folder.id, name.trim());
      onChanged();
    } catch (error) {
      toast.error(errorMessage(error));
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await sharedApi.deleteFolder(folder.id);
      toast.success('Folder deleted.');
      setConfirming(false);
      onChanged();
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="folder-actions">
      <Button variant="ghost" size="sm" onClick={rename}>
        Rename
      </Button>
      <Button variant="ghost" size="sm" onClick={() => setConfirming(true)}>
        Delete
      </Button>
      <ConfirmDialog
        open={confirming}
        title={`Delete “${folder.name}”?`}
        message="Only empty folders can be deleted. Games are never deleted with a folder."
        confirmLabel="Delete folder"
        tone="danger"
        busy={busy}
        onConfirm={remove}
        onCancel={() => setConfirming(false)}
      />
    </span>
  );
}
