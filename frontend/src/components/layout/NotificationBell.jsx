import { Link } from '../../routes/router';
import { useUnreadCount } from '../../store/notificationStore';

export default function NotificationBell({ to }) {
  const unread = useUnreadCount();
  const label = unread ? `Notifications, ${unread} unread` : 'Notifications';

  return (
    <Link to={to} className="notification-bell" aria-label={label} title={label}>
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4zM10 20a2 2 0 0 0 4 0" />
      </svg>
      {unread > 0 && <span className="notification-badge">{unread > 99 ? '99+' : unread}</span>}
    </Link>
  );
}
