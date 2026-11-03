import { useAuth } from '../../store/authStore';
import AccountMenu from './AccountMenu';
import BottomNav from './BottomNav';
import NotificationBell from './NotificationBell';
import Sidebar from './Sidebar';
import ThemeToggle from './ThemeToggle';

export default function AppShell({ nav, children }) {
  const { user, logout } = useAuth();

  return (
    <div className="app-shell">
      <a
        href="#main-content"
        className="skip-link"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById('main-content')?.focus();
        }}
      >
        Skip to content
      </a>
      <Sidebar nav={nav} user={user} onSignOut={logout} />
      <main id="main-content" className="app-main" tabIndex={-1}>
        <div className="mobile-topbar">
          {user && <NotificationBell to={`/${user.role}/notifications`} />}
          <ThemeToggle />
          {user && <AccountMenu nav={nav} user={user} onSignOut={logout} />}
        </div>
        {children}
      </main>
      <BottomNav nav={nav} />
    </div>
  );
}
