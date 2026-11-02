import { useAuth } from '../store/authStore';
import EmptyState from '../components/ui/EmptyState';

/**
 * Renders children only for the given roles. This is a convenience for the
 * UI; every rule is enforced again by the API.
 */
export default function ProtectedRoute({ roles, children }) {
  const { user } = useAuth();

  if (!user || (roles && !roles.includes(user.role))) {
    return (
      <EmptyState
        title="You cannot open this page"
        message="Your account does not have access to it."
      />
    );
  }

  return children;
}
