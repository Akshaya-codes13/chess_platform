import DashboardPage from './DashboardPage';
import GroupDetailPage from './GroupDetailPage';
import GroupsPage from './GroupsPage';
import PuzzleDetailPage from './PuzzleDetailPage';
import PuzzlesPage from './PuzzlesPage';
import ReportsPage from './ReportsPage';
import StudentsPage from './StudentsPage';
import TrainersPage from './TrainersPage';
import UserDetailPage from './UserDetailPage';
import UsersPage from './UsersPage';

// Registered for users whose role is `admin` by the shared AppRouter. The
// dashboard lives at /admin/dashboard so the "/admin" prefix does not mark
// it active on every page; "/admin" is kept as an alias. Trainer and student
// detail pages share one component; IDs are user IDs.
export const adminRoutes = [
  { path: '/admin', element: DashboardPage, title: 'Admin dashboard' },
  { path: '/admin/dashboard', element: DashboardPage, title: 'Admin dashboard' },
  { path: '/admin/users', element: UsersPage, title: 'Users' },
  { path: '/admin/users/:userId', element: UserDetailPage, title: 'User' },
  { path: '/admin/trainers', element: TrainersPage, title: 'Trainers' },
  { path: '/admin/trainers/:userId', element: UserDetailPage, title: 'Trainer' },
  { path: '/admin/students', element: StudentsPage, title: 'Students' },
  { path: '/admin/students/:userId', element: UserDetailPage, title: 'Student' },
  { path: '/admin/groups', element: GroupsPage, title: 'Groups' },
  { path: '/admin/groups/:groupId', element: GroupDetailPage, title: 'Group' },
  { path: '/admin/puzzles', element: PuzzlesPage, title: 'Puzzles' },
  { path: '/admin/puzzles/:puzzleId', element: PuzzleDetailPage, title: 'Puzzle' },
  { path: '/admin/reports', element: ReportsPage, title: 'Reports' },
];

export const adminNav = [
  { to: '/admin/dashboard', label: 'Dashboard', icon: 'home', primary: true },
  { to: '/admin/users', label: 'Users', icon: 'users', primary: true },
  { to: '/admin/trainers', label: 'Trainers', icon: 'profile' },
  { to: '/admin/students', label: 'Students', icon: 'progress' },
  { to: '/admin/groups', label: 'Groups', icon: 'groups', primary: true },
  { to: '/admin/puzzles', label: 'Puzzles', icon: 'puzzle', primary: true },
  { to: '/admin/reports', label: 'Reports', icon: 'reports', primary: true },
];
