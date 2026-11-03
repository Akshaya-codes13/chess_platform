import { api } from '../../api/client';

const post = (path, body) => api(path, { method: 'POST', body });
const patch = (path, body) => api(path, { method: 'PATCH', body });
const remove = (path) => api(path, { method: 'DELETE' });

/** Endpoints shared by every role: account, notifications, games, content, feedback. */
export const sharedApi = {
  settings: () => api('/account/settings'),
  updateSettings: (body) => patch('/account/settings', body),
  changePassword: (body) => post('/account/password', body),

  notifications: (query) => api('/notifications', { query }),
  unreadCount: () => api('/notifications/unread-count'),
  markRead: (id) => post(`/notifications/${id}/read`),
  markAllRead: () => post('/notifications/read-all'),

  gameDatabases: () => api('/games/databases'),
  createGameDatabase: (body) => post('/games/databases', body),
  updateGameDatabase: (id, body) => patch(`/games/databases/${id}`, body),
  deleteGameDatabase: (id) => remove(`/games/databases/${id}`),
  browse: (id, query) => api(`/games/databases/${id}/browse`, { query }),
  createFolder: (id, body) => post(`/games/databases/${id}/folders`, body),
  renameFolder: (id, name) => patch(`/games/folders/${id}`, { name }),
  deleteFolder: (id) => remove(`/games/folders/${id}`),
  importPgn: (id, form) => api(`/games/databases/${id}/import`, { method: 'POST', body: form }),
  game: (id) => api(`/games/${id}`),
  moveGame: (id, folderId) => patch(`/games/${id}`, { folder_id: folderId }),
  deleteGame: (id) => remove(`/games/${id}`),

  posts: (query) => api('/content/posts', { query }),
  post: (id) => api(`/content/posts/${id}`),
  createPost: (body) => post('/content/posts', body),
  updatePost: (id, body) => patch(`/content/posts/${id}`, body),
  postAction: (id, action) => post(`/content/posts/${id}/${action}`),
  deletePost: (id) => remove(`/content/posts/${id}`),
  uploadImage: (file) => {
    const form = new FormData();
    form.append('file', file);
    return api('/content/media', { method: 'POST', body: form });
  },

  feedbackRecipients: () => api('/feedback/recipients'),
  feedback: (query) => api('/feedback', { query }),
  sendFeedback: (body) => post('/feedback', body),
  reviewFeedback: (id, response) => post(`/feedback/${id}/review`, { response }),
};
