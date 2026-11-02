import { useAuth } from '../../store/authStore';
import BottomNav from './BottomNav';
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
          <ThemeToggle />
        </div>
        {children}
      </main>
      <BottomNav nav={nav} />
    </div>
  );
}
