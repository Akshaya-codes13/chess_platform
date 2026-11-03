import { useAuth } from '../../store/authStore';

/** Path prefix of the signed-in user's portal, e.g. "/trainer". */
export function usePortalBase() {
  const { user } = useAuth();
  return `/${user?.role ?? 'student'}`;
}

export function useRole() {
  return useAuth().user?.role ?? null;
}
