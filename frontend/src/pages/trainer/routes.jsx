/* eslint-disable react-refresh/only-export-components -- route table; lazy pages are not exported */
import { lazy } from 'react';
import AssignmentFormPage from './AssignmentFormPage';
import AssignmentProgressPage from './AssignmentProgressPage';
import AssignmentsPage from './AssignmentsPage';
import DashboardPage from './DashboardPage';
import GroupDetailPage from './GroupDetailPage';
import GroupsPage from './GroupsPage';
import ProfilePage from './ProfilePage';
import PuzzleDetailPage from './PuzzleDetailPage';
import PuzzleFormPage from './PuzzleFormPage';
import PuzzleLibraryPage from './PuzzleLibraryPage';
import SessionDetailPage from './SessionDetailPage';
import SessionFormPage from './SessionFormPage';
import SessionsPage from './SessionsPage';
import StudentPerformancePage from './StudentPerformancePage';
const ReportsPage = lazy(() => import('./ReportsPage'));
const SubmissionReviewPage = lazy(() => import('./SubmissionReviewPage'));

// Static segments ("new") are listed before parameterised ones. The
// dashboard lives at /trainer/dashboard so the "/trainer" prefix does not
// mark it active on every page; "/trainer" is kept as an alias.
export const trainerRoutes = [
  { path: '/trainer', element: DashboardPage, title: 'Dashboard' },
  { path: '/trainer/dashboard', element: DashboardPage, title: 'Dashboard' },
  { path: '/trainer/groups', element: GroupsPage, title: 'My groups' },
  { path: '/trainer/groups/:groupId', element: GroupDetailPage, title: 'Group' },
  {
    path: '/trainer/students/:studentId',
    element: StudentPerformancePage,
    title: 'Student performance',
  },
  { path: '/trainer/puzzles', element: PuzzleLibraryPage, title: 'Puzzle library' },
  { path: '/trainer/puzzles/new', element: PuzzleFormPage, title: 'Create puzzle' },
  { path: '/trainer/puzzles/:puzzleId', element: PuzzleDetailPage, title: 'Puzzle' },
  { path: '/trainer/puzzles/:puzzleId/edit', element: PuzzleFormPage, title: 'Edit puzzle' },
  { path: '/trainer/assignments', element: AssignmentsPage, title: 'Assignments' },
  { path: '/trainer/assignments/new', element: AssignmentFormPage, title: 'New assignment' },
  {
    path: '/trainer/assignments/:assignmentId',
    element: AssignmentProgressPage,
    title: 'Assignment',
  },
  {
    path: '/trainer/assignments/:assignmentId/edit',
    element: AssignmentFormPage,
    title: 'Edit assignment',
  },
  { path: '/trainer/sessions', element: SessionsPage, title: 'Sessions' },
  { path: '/trainer/sessions/new', element: SessionFormPage, title: 'Schedule session' },
  { path: '/trainer/sessions/:sessionId', element: SessionDetailPage, title: 'Session' },
  { path: '/trainer/sessions/:sessionId/edit', element: SessionFormPage, title: 'Edit session' },
  {
    path: '/trainer/assignments/:assignmentId/submissions/:studentId',
    element: SubmissionReviewPage,
    title: 'Submission',
  },
  { path: '/trainer/reports', element: ReportsPage, title: 'Reports' },
  { path: '/trainer/profile', element: ProfilePage, title: 'Profile' },
];

export const trainerNav = [
  { to: '/trainer/dashboard', label: 'Dashboard', icon: 'home' },
  { to: '/trainer/groups', label: 'Groups', icon: 'groups' },
  { to: '/trainer/puzzles', label: 'Puzzles', icon: 'puzzle' },
  { to: '/trainer/assignments', label: 'Assignments', icon: 'assignments' },
  { to: '/trainer/sessions', label: 'Sessions', icon: 'schedule' },
  { to: '/trainer/reports', label: 'Reports', icon: 'statistics' },
  { to: '/trainer/profile', label: 'Profile', icon: 'profile' },
];
