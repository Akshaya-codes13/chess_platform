import { Link } from '../../routes/router';

export default function PageHeader({ title, subtitle, actions, back }) {
  return (
    <header className="page-header">
      <div>
        {back && (
          <Link to={back.to} className="back-link">
            {back.label}
          </Link>
        )}
        <h1>{title}</h1>
        {subtitle && <p className="page-subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}
