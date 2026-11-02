export default function EmptyState({ title, message, action }) {
  return (
    <div className="empty-state">
      <p className="empty-title">{title}</p>
      {message && <p className="empty-message">{message}</p>}
      {action && <div className="empty-action">{action}</div>}
    </div>
  );
}
