import { api } from '../../api/client';

// Thin wrappers over the shared API client for the /admin endpoints.
// List endpoints return { items, total, page, page_size, pages }. Trainer
// and student IDs are always user IDs.

const post = (path, body) => api(path, { method: 'POST', body });
const patch = (path, body) => api(path, { method: 'PATCH', body });

export const adminApi = {
  dashboard: () => api('/admin/dashboard'),
  activity: (query) => api('/admin/activity', { query }),
  reports: () => api('/admin/reports/overview'),

  users: (query) => api('/admin/users', { query }),
  user: (id) => api(`/admin/users/${id}`),
  createUser: (body) => post('/admin/users', body),
  updateUser: (id, body) => patch(`/admin/users/${id}`, body),
  changeRole: (id, body) => patch(`/admin/users/${id}/role`, body),
  changeStatus: (id, isActive) => patch(`/admin/users/${id}/status`, { is_active: isActive }),

  trainers: (query) => api('/admin/trainers', { query }),
  students: (query) => api('/admin/students', { query }),

  groups: (query) => api('/admin/groups', { query }),
  group: (id) => api(`/admin/groups/${id}`),
  createGroup: (body) => post('/admin/groups', body),
  updateGroup: (id, body) => patch(`/admin/groups/${id}`, body),
  assignTrainer: (id, trainerUserId) =>
    api(`/admin/groups/${id}/trainer`, { method: 'PUT', body: { trainer_user_id: trainerUserId } }),
  addStudents: (id, studentUserIds) =>
    post(`/admin/groups/${id}/students`, { student_user_ids: studentUserIds }),
  removeStudent: (id, studentUserId) =>
    api(`/admin/groups/${id}/students/${studentUserId}`, { method: 'DELETE' }),

  puzzleFilters: () => api('/admin/puzzles/filters'),
  puzzles: (query) => api('/admin/puzzles', { query }),
  puzzle: (id) => api(`/admin/puzzles/${id}`),
  puzzleAction: (id, action) => post(`/admin/puzzles/${id}/${action}`),

  assignments: (query) => api('/admin/assignments', { query }),
  sessions: (query) => api('/admin/sessions', { query }),
};
