import { apiClient } from './client';

export const notificationsApi = {
  getPreferences: () => apiClient.get('/api/notifications/preferences'),
  updatePreferences: (data) => apiClient.put('/api/notifications/preferences', data),
  getHistory: () => apiClient.get('/api/notifications/history'),
};
