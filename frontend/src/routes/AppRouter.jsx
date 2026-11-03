import { Fragment, Suspense, useEffect } from 'react';
import AppShell from '../components/layout/AppShell';
import Button from '../components/ui/Button';
import EmptyState from '../components/ui/EmptyState';
import Spinner from '../components/ui/Spinner';
import LoginPage from '../pages/LoginPage';
import { adminNav, adminRoutes } from '../pages/admin/routes';
import { sharedNav, sharedRoutes } from '../pages/shared/routes';
import StudentAccessGate from '../pages/student/AccessGate';
import { studentNav, studentRoutes } from '../pages/student/routes';
import { useAuth } from '../store/authStore';
import { matchRoute, navigate, setActiveRoutes, useLocation } from './router';

// The Trainer module (M5) registers its pages in src/pages/trainer/routes.jsx.
// A glob import keeps the app building whether or not that file exists yet.
const trainerModule = Object.values(
  import.meta.glob('../pages/trainer/routes.jsx', { eager: true }),
)[0];

const PORTALS = {
  // The gate holds new students on a waiting screen until a trainer is assigned.
  student: {
    home: '/student/dashboard',
    routes: studentRoutes,
    nav: studentNav,
    gate: StudentAccessGate,
  },
  trainer: {
    home: '/trainer/dashboard',
    routes: trainerModule?.trainerRoutes ?? [],
    nav: trainerModule?.trainerNav ?? [],
  },
  admin: { home: '/admin/dashboard', routes: adminRoutes, nav: adminNav },
};

// Settings, notifications, games, library and feedback exist in every portal.
Object.entries(PORTALS).forEach(([role, portal]) => {
  if (!portal.routes.length) return;
  portal.routes = [...portal.routes, ...sharedRoutes(role)];
  portal.nav = [...portal.nav, ...sharedNav(role)];
});

function Redirect({ to }) {
  useEffect(() => navigate(to, { replace: true }), [to]);
  return <Spinner />;
}

function DocumentTitle({ title }) {
  useEffect(() => {
    document.title = title ? `${title} · Chess Academy` : 'Chess Academy';
  }, [title]);
  return null;
}

function PortalUnavailable({ role }) {
  const { logout } = useAuth();
  return (
    <main className="standalone">
      <EmptyState
        title={`The ${role} portal is not available yet`}
        message="You are signed in, but this part of the academy has not been released. Sign in with a student account to use the student portal."
        action={<Button onClick={logout}>Sign out</Button>}
      />
    </main>
  );
}

export default function AppRouter() {
  const { status, user } = useAuth();
  const { path } = useLocation();

  if (status === 'loading') {
    return (
      <main className="standalone">
        <Spinner label="Restoring your session" />
      </main>
    );
  }

  if (status !== 'authenticated') return <LoginPage />;

  const portal = PORTALS[user.role];
  if (!portal || !portal.routes.length) return <PortalUnavailable role={user.role} />;

  setActiveRoutes(portal.routes);
  const Gate = portal.gate ?? Fragment;

  return (
    <Gate>
      <PortalPage portal={portal} path={path} />
    </Gate>
  );
}

function PortalPage({ portal, path }) {
  const match = matchRoute(portal.routes, path);

  if (path === '/' || path === '/login') return <Redirect to={portal.home} />;

  if (!match) {
    return (
      <AppShell nav={portal.nav}>
        <EmptyState
          title="Page not found"
          message="This address does not match a page you can open."
          action={<Button to={portal.home}>Go to your dashboard</Button>}
        />
      </AppShell>
    );
  }

  const Page = match.route.element;

  return (
    <AppShell nav={portal.nav}>
      <DocumentTitle title={match.route.title} />
      <Suspense fallback={<Spinner />}>
        <Page key={path} />
      </Suspense>
    </AppShell>
  );
}
