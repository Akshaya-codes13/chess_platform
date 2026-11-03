import { lazy } from 'react';

// Loaded on demand: these pages bring the board, engine and chart libraries.
const BoardEditorPage = lazy(() => import('./BoardEditorPage'));
const FeedbackPage = lazy(() => import('./FeedbackPage'));
const GameBrowserPage = lazy(() => import('./GameBrowserPage'));
const GameDatabasesPage = lazy(() => import('./GameDatabasesPage'));
const GameViewerPage = lazy(() => import('./GameViewerPage'));
const NotificationsPage = lazy(() => import('./NotificationsPage'));
const PostEditorPage = lazy(() => import('./PostEditorPage'));
const PostPage = lazy(() => import('./PostPage'));
const PostsPage = lazy(() => import('./PostsPage'));
const SettingsPage = lazy(() => import('./SettingsPage'));

/**
 * Pages every role has, mounted under the role's own prefix ("/trainer/…")
 * so the sidebar highlights them like the portal's other pages. The backend
 * enforces what each role may do on them.
 */
export function sharedRoutes(role) {
  const base = `/${role}`;
  const routes = [
    { path: `${base}/settings`, element: SettingsPage, title: 'Settings' },
    { path: `${base}/notifications`, element: NotificationsPage, title: 'Notifications' },
    { path: `${base}/games`, element: GameDatabasesPage, title: 'Game database' },
    { path: `${base}/games/db/:databaseId`, element: GameBrowserPage, title: 'Game database' },
    { path: `${base}/games/view/:gameId`, element: GameViewerPage, title: 'Game' },
    { path: `${base}/board-editor`, element: BoardEditorPage, title: 'Board editor' },
    { path: `${base}/content`, element: PostsPage, title: 'Academy library' },
    { path: `${base}/content/:postId`, element: PostPage, title: 'Post' },
    { path: `${base}/feedback`, element: FeedbackPage, title: 'Feedback' },
  ];

  if (role !== 'student') {
    // Static "new" before the parameterised post route.
    routes.splice(
      routes.findIndex((route) => route.path === `${base}/content/:postId`),
      0,
      { path: `${base}/content/new`, element: PostEditorPage, title: 'New post' },
    );
    routes.push({
      path: `${base}/content/:postId/edit`,
      element: PostEditorPage,
      title: 'Edit post',
    });
  }

  return routes;
}

export function sharedNav(role) {
  const base = `/${role}`;
  return [
    { to: `${base}/games`, label: 'Game database', icon: 'games' },
    { to: `${base}/content`, label: 'Library', icon: 'content' },
    { to: `${base}/feedback`, label: 'Feedback', icon: 'feedback' },
  ];
}
