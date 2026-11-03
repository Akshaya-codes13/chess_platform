import { useEffect, useRef } from 'react';
import { isActive, Link, useLocation } from '../../routes/router';
import { bottomNavItems } from './bottomNavItems';
import NavIcon from './NavIcon';

/**
 * Mobile "more" menu (three dots, top right): the pages that don't fit in the
 * bottom bar, plus the sidebar's Settings / Sign out, which is hidden on small screens.
 */
export default function AccountMenu({ nav, user, onSignOut }) {
  const ref = useRef(null);
  const { path } = useLocation();
  const settingsPath = `/${user.role}/settings`;
  const shown = new Set(bottomNavItems(nav).map((item) => item.to));
  const pages = nav.filter((item) => !shown.has(item.to) && item.to !== settingsPath);

  // Close on navigation and on outside click.
  useEffect(() => {
    if (ref.current) ref.current.open = false;
  }, [path]);

  useEffect(() => {
    const close = (e) => {
      if (ref.current && !ref.current.contains(e.target)) ref.current.open = false;
    };
    document.addEventListener('click', close);
    return () => document.removeEventListener('click', close);
  }, []);

  return (
    <details className="account-menu" ref={ref}>
      <summary aria-label="More pages and account" title="More">
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <circle cx="12" cy="5" r="1.6" />
          <circle cx="12" cy="12" r="1.6" />
          <circle cx="12" cy="19" r="1.6" />
        </svg>
      </summary>
      <div className="account-menu-panel">
        <span className="account-menu-name">{user.full_name}</span>
        {pages.length > 0 && (
          <nav aria-label="More pages" className="account-menu-pages">
            {pages.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className={`account-menu-item ${isActive(path, item.to) ? 'is-active' : ''}`}
                aria-current={isActive(path, item.to) ? 'page' : undefined}
              >
                <NavIcon name={item.icon} />
                {item.label}
              </Link>
            ))}
          </nav>
        )}
        <Link
          to={settingsPath}
          className={`account-menu-item ${isActive(path, settingsPath) ? 'is-active' : ''}`}
        >
          Settings
        </Link>
        <button type="button" className="account-menu-item" onClick={onSignOut}>
          Sign out
        </button>
      </div>
    </details>
  );
}
