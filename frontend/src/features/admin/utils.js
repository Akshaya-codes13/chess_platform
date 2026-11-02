import { errorMessage } from '../trainer/api';
import { titleCase } from '../trainer/format';
import { toast } from '../trainer/components/toastStore';

export const ROLE_OPTIONS = [
  { value: 'admin', label: 'Admin' },
  { value: 'trainer', label: 'Trainer' },
  { value: 'student', label: 'Student' },
];

export const STATUS_OPTIONS = [
  { value: 'true', label: 'Active' },
  { value: 'false', label: 'Inactive' },
];

export const LEVEL_OPTIONS = ['beginner', 'intermediate', 'advanced', 'expert'].map((value) => ({
  value,
  label: titleCase(value),
}));

/** Path to the most specific detail page for a user. */
export function userPath(user) {
  if (user.role === 'trainer') return `/admin/trainers/${user.id}`;
  if (user.role === 'student') return `/admin/students/${user.id}`;
  return `/admin/users/${user.id}`;
}

/** "group.students_added" -> "Group students added". */
export function activityLabel(action) {
  return titleCase(action.replace('.', ' '));
}

const ENTITY_PATHS = { user: '/admin/users', group: '/admin/groups', puzzle: '/admin/puzzles' };

/** Detail page for an audit-log entity, or null when there is none. */
export function entityPath(entityType, entityId) {
  return ENTITY_PATHS[entityType] && entityId ? `${ENTITY_PATHS[entityType]}/${entityId}` : null;
}

/** Run a one-off action (status change, removal) with toasts. */
export async function runAction(action, successMessage) {
  try {
    const result = await action();
    toast.success(successMessage);
    return result ?? true;
  } catch (error) {
    toast.error(errorMessage(error));
    return undefined;
  }
}

/** Drop empty strings so optional fields are sent as absent, not "". */
export function compact(values) {
  return Object.fromEntries(
    Object.entries(values).filter(([, value]) => value !== '' && value !== undefined),
  );
}
