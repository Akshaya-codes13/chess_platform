import { isActive, Link, useLocation } from '../../routes/router';
import NavIcon from './NavIcon';

/** Mobile navigation: the items flagged `primary`, or the first five. */
export default function BottomNav({ nav }) {
  const { path } = useLocation();
  const primary = nav.filter((item) => item.primary);
  const items = (primary.length ? primary : nav).slice(0, 5);

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
