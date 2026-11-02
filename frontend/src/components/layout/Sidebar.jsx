import { isActive, Link, useLocation } from '../../routes/router';
import NavIcon from './NavIcon';
import ThemeToggle from './ThemeToggle';

export default function Sidebar({ nav, user, onSignOut }) {
  const { path } = useLocation();

  return (
    <aside className="sidebar">
      <Link to="/" className="brand">
        <span className="brand-mark" aria-hidden="true">
          ♞&#xFE0E;
        </span>
        <span className="brand-name">Chess Academy</span>
      </Link>

      <nav aria-label="Main">
        <ul className="sidebar-nav">
          {nav.map((item) => (
            <li key={item.to}>
              <Link
                to={item.to}
                className={`sidebar-link ${isActive(path, item.to) ? 'is-active' : ''}`}
                aria-current={isActive(path, item.to) ? 'page' : undefined}
              >
                <NavIcon name={item.icon} />
                {item.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>

      {user && (
        <div className="sidebar-user">
          <div className="sidebar-theme">
            <ThemeToggle />
          </div>
          <span className="sidebar-user-name">{user.full_name}</span>
          <button type="button" className="link-button" onClick={onSignOut}>
            Sign out
          </button>
        </div>
      )}
    </aside>
  );
}
