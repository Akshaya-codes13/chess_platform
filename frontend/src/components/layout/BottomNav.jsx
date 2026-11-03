import { isActive, Link, useLocation } from '../../routes/router';
import { bottomNavItems } from './bottomNavItems';
import NavIcon from './NavIcon';

/** Mobile navigation; whatever doesn't fit lives in the top-right AccountMenu. */
export default function BottomNav({ nav }) {
  const { path } = useLocation();
  const items = bottomNavItems(nav);

  return (
    <nav className="bottom-nav" aria-label="Main">
      {items.map((item) => (
        <Link
          key={item.to}
          to={item.to}
          className={`bottom-link ${isActive(path, item.to) ? 'is-active' : ''}`}
          aria-current={isActive(path, item.to) ? 'page' : undefined}
        >
          <NavIcon name={item.icon} />
          <span>{item.shortLabel ?? item.label}</span>
        </Link>
      ))}
    </nav>
  );
}
