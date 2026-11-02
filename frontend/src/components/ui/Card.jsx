export default function Card({ title, actions, children, className = '', as: Tag = 'section' }) {
  return (
    <Tag className={`card ${className}`.trim()}>
      {(title || actions) && (
        <header className="card-header">
          {title && <h2 className="card-title">{title}</h2>}
          {actions && <div className="card-actions">{actions}</div>}
        </header>
      )}
      {children}
    </Tag>
  );
}
