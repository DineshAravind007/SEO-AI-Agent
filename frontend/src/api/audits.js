import { apiClient } from './client';

export const auditsApi = {
  createAudit: async (url, maxPages = 10, maxDepth = 2) => {
    return await apiClient.post('/api/audits', { url, max_pages: maxPages, max_depth: maxDepth });
  },

  getAudit: async (auditId) => {
    return await apiClient.get(`/api/audits/${auditId}`);
  },

  getAuditPages: async (auditId) => {
    return await apiClient.get(`/api/audits/${auditId}/pages`);
  },

  getAuditIssues: async (auditId) => {
    return await apiClient.get(`/api/audits/${auditId}/issues`);
  },

  getAuditScore: async (auditId) => {
    return await apiClient.get(`/api/audits/${auditId}/score`);
  },

  getRecommendations: async (auditId) => {
    return await apiClient.get(`/api/audits/${auditId}/recommendations`);
  },

  generateRecommendations: async (auditId) => {
    return await apiClient.post(`/api/audits/${auditId}/recommendations`, {});
  },
};
