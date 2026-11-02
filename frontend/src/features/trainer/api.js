import { api } from '../../api/client';

// Thin wrappers over the shared API client for the /trainer endpoints.
// Every list endpoint returns { items, total, page, page_size, pages }.

const post = (path, body) => api(path, { method: 'POST', body });
const patch = (path, body) => api(path, { method: 'PATCH', body });

export const trainerApi = {
  dashboard: () => api('/trainer/dashboard'),

  profile: () => api('/trainer/profile'),
  updateProfile: (body) => patch('/trainer/profile', body),
  requestPasswordReset: (email) => post('/auth/password-reset/request', { email }),

  groups: (query) => api('/trainer/groups', { query }),
  group: (id) => api(`/trainer/groups/${id}`),
  groupStudents: (id, query) => api(`/trainer/groups/${id}/students`, { query }),
  groupAssignments: (id, query) => api(`/trainer/groups/${id}/assignments`, { query }),
  groupPerformance: (id) => api(`/trainer/groups/${id}/performance`),
  studentPerformance: (id) => api(`/trainer/students/${id}/performance`),

  taxonomy: () => api('/trainer/puzzle-taxonomy'),
  puzzles: (query) => api('/trainer/puzzles', { query }),
  puzzle: (id) => api(`/trainer/puzzles/${id}`),
  validatePuzzle: (body) => post('/trainer/puzzles/validate', body),
  createPuzzle: (body) => post('/trainer/puzzles', body),
  updatePuzzle: (id, body) => patch(`/trainer/puzzles/${id}`, body),
  puzzleAction: (id, action) => post(`/trainer/puzzles/${id}/${action}`),

  assignments: (query) => api('/trainer/assignments', { query }),
  assignment: (id) => api(`/trainer/assignments/${id}`),
  assignmentProgress: (id) => api(`/trainer/assignments/${id}/progress`),
  createAssignment: (body) => post('/trainer/assignments', body),
  updateAssignment: (id, body) => patch(`/trainer/assignments/${id}`, body),
  assignmentAction: (id, action) => post(`/trainer/assignments/${id}/${action}`),

  sessions: (query) => api('/trainer/sessions', { query }),
  session: (id) => api(`/trainer/sessions/${id}`),
  createSession: (body) => post('/trainer/sessions', body),
  updateSession: (id, body) => patch(`/trainer/sessions/${id}`, body),
  sessionAction: (id, action) => post(`/trainer/sessions/${id}/${action}`),
  recordAttendance: (id, records) => post(`/trainer/sessions/${id}/attendance`, { records }),
};

/** Turn an ApiError (string or FastAPI 422 list detail) into readable text. */
export function errorMessage(error) {
  const detail = error?.detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const field = item.loc?.filter((part) => part !== 'body').join('.');
        const message = (item.msg || '').replace(/^Value error, /, '');
        return field ? `${field}: ${message}` : message;
      })
      .join(' ');
  }
  if (typeof detail === 'string') return detail;
  return error?.message || 'Something went wrong.';
}

/** Map a 422 list detail to { fieldName: message } for inline form errors. */
export function fieldErrors(error) {
  if (!Array.isArray(error?.detail)) return {};
  const errors = {};
  for (const item of error.detail) {
    const field = item.loc?.[1];
    if (field && !errors[field]) errors[field] = (item.msg || '').replace(/^Value error, /, '');
  }
  return errors;
}
