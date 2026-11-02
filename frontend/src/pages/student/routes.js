import AchievementsPage from './AchievementsPage';
import AssignmentDetailPage from './AssignmentDetailPage';
import AssignmentsPage from './AssignmentsPage';
import AttendancePage from './AttendancePage';
import BadgesPage from './BadgesPage';
import DashboardPage from './DashboardPage';
import GroupDetailPage from './GroupDetailPage';
import GroupsPage from './GroupsPage';
import ProfilePage from './ProfilePage';
import ProgressPage from './ProgressPage';
import PuzzlePage from './PuzzlePage';
import SessionDetailPage from './SessionDetailPage';
import SessionsPage from './SessionsPage';

export const studentRoutes = [
  { path: '/student/dashboard', element: DashboardPage, title: 'Dashboard' },
  { path: '/student/profile', element: ProfilePage, title: 'Profile' },
  { path: '/student/groups', element: GroupsPage, title: 'My groups' },
  { path: '/student/groups/:groupId', element: GroupDetailPage, title: 'Group' },
  { path: '/student/assignments', element: AssignmentsPage, title: 'Assignments' },
  {
    path: '/student/assignments/:assignmentId',
    element: AssignmentDetailPage,
    title: 'Assignment',
  },
  {
    path: '/student/assignments/:assignmentId/puzzles/:puzzleId',
    element: PuzzlePage,
    title: 'Puzzle',
  },
  { path: '/student/sessions', element: SessionsPage, title: 'Class schedule' },
  { path: '/student/sessions/:sessionId', element: SessionDetailPage, title: 'Class' },
  { path: '/student/attendance', element: AttendancePage, title: 'Attendance' },
  { path: '/student/progress', element: ProgressPage, title: 'Progress' },
  { path: '/student/achievements', element: AchievementsPage, title: 'XP and achievements' },
  { path: '/student/badges', element: BadgesPage, title: 'Badges' },
];

// `primary` items also appear in the mobile bottom bar.
export const studentNav = [
  { to: '/student/dashboard', label: 'Dashboard', shortLabel: 'Home', icon: 'home', primary: true },
  {
    to: '/student/assignments',
    label: 'Assignments',
    shortLabel: 'Work',
    icon: 'assignments',
    primary: true,
  },
  { to: '/student/groups', label: 'My groups', icon: 'groups' },
  {
    to: '/student/sessions',
    label: 'Class schedule',
    shortLabel: 'Classes',
    icon: 'schedule',
    primary: true,
  },
  { to: '/student/attendance', label: 'Attendance', icon: 'attendance' },
  { to: '/student/progress', label: 'Progress', icon: 'progress', primary: true },
  { to: '/student/achievements', label: 'XP and badges', icon: 'achievements' },
  { to: '/student/profile', label: 'Profile', icon: 'profile', primary: true },
];
