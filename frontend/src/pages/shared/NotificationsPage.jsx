import { useState } from 'react';
import { errorMessage } from '../../features/trainer/api';
import Pagination from '../../features/trainer/components/Pagination';
import TrainerPage from '../../features/trainer/components/TrainerPage';
import { toast } from '../../features/trainer/components/toastStore';
import { Button, Empty, Loaded, PageHeader, Section } from '../../features/trainer/components/ui';
import { formatDateTime } from '../../features/trainer/format';
import { useLoader } from '../../features/trainer/hooks';
import { sharedApi } from '../../features/shared/api';
import { navigate } from '../../routes/router';
import { refreshUnreadCount } from '../../store/notificationStore';
import { usePortalBase } from './base';

/** Where a notification leads, per role, from the ids in its data. */
function targetPath(base, note) {
  const data = note.data ?? {};
  if (data.session_id) return `${base}/sessions/${data.session_id}`;
  if (data.assignment_id && data.student_id && base === '/trainer')
    return `/trainer/assignments/${data.assignment_id}`;
  if (data.assignment_id) return `${base}/assignments/${data.assignment_id}`;
  if (data.post_id) return `${base}/content/${data.post_id}`;
  if (data.feedback_id) return `${base}/feedback`;
  return null;
}

export default function NotificationsPage() {
  const base = usePortalBase();
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [page, setPage] = useState(1);
  const result = useLoader(
    () => sharedApi.notifications({ unread_only: unreadOnly, page, page_size: 20 }),
    [unreadOnly, page],
  );

  async function open(note) {
    try {
      if (!note.is_read) await sharedApi.markRead(note.id);
      refreshUnreadCount();
    } catch {
      // Opening the target still makes sense if marking failed.
    }
    const path = targetPath(base, note);
    if (path) navigate(path);
    else result.reload();
  }

  async function markAll() {
    try {
      const { marked } = await sharedApi.markAllRead();
      toast.success(marked ? `Marked ${marked} as read.` : 'Nothing to mark.');
      refreshUnreadCount();
      result.reload();
    } catch (error) {
      toast.error(errorMessage(error));
    }
  }

  return (
    <TrainerPage>
      <PageHeader
        title="Notifications"
        actions={
          <>
            <label className="tr-checkbox">
              <input
                type="checkbox"
                checked={unreadOnly}
                onChange={(event) => {
                  setUnreadOnly(event.target.checked);
                  setPage(1);
                }}
              />
              <span>Unread only</span>
            </label>
            <Button variant="secondary" size="sm" onClick={markAll}>
              Mark all as read
            </Button>
          </>
        }
      />
      <Loaded result={result}>
        {(data) =>
          data.items.length === 0 ? (
            <Empty
              title={unreadOnly ? 'No unread notifications' : 'No notifications yet'}
              message="Class changes, assignments, feedback and new posts appear here."
            />
          ) : (
            <Section>
              <ul className="notification-list">
                {data.items.map((note) => (
                  <li key={note.id} className={note.is_read ? '' : 'is-unread'}>
                    <button type="button" className="notification-item" onClick={() => open(note)}>
                      <span className="notification-title">
                        {!note.is_read && <span className="unread-dot" aria-label="Unread" />}
                        {note.title}
                      </span>
                      <span className="tr-muted">{note.message}</span>
                      <span className="tr-muted notification-time">
                        {formatDateTime(note.created_at)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
              <Pagination
                page={data.page}
                pages={data.pages}
                total={data.total}
                onChange={setPage}
                label="notifications"
              />
            </Section>
          )
        }
      </Loaded>
    </TrainerPage>
  );
}
