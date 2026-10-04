import { apiClient } from './client';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const auditsApi = {
  createAudit: async (url, maxPages = 10, maxDepth = 2) => {
    return await apiClient.post('/api/audits', { url, max_pages: maxPages, max_depth: maxDepth });
  },

  /** Return paginated list of all audits (newest first). */
  getAudits: async ({ skip = 0, limit = 50 } = {}) => {
    return await apiClient.get(`/api/audits?skip=${skip}&limit=${limit}`);
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

  /**
   * Download the HTML report for a completed audit.
   * Uses a direct window fetch + anchor trick to trigger a file download
   * without navigating away from the current page.
   */
  downloadAuditReport: async (auditId) => {
    const url = `${BASE_URL}/api/audits/${auditId}/report`;
    const response = await fetch(url, { method: 'GET' });

    if (!response.ok) {
      let detail = `HTTP ${response.status}`;
      try {
        const json = await response.json();
        detail = json.detail || detail;
      } catch (_) {}
      throw new Error(detail);
    }

    // Extract filename from Content-Disposition header if available
    const disposition = response.headers.get('content-disposition') || '';
    const match = disposition.match(/filename="?([^"]+)"?/);
    const filename = match ? match[1] : `seo-report-audit-${auditId}.html`;

    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = objectUrl;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(objectUrl);
  },
  /**
   * Add competitors to an audit.
   * @param {number} auditId 
   * @param {string[]} urls 
   */
  addCompetitors: async (auditId, urls) => {
    return await apiClient.post(`/api/audits/${auditId}/competitors`, { urls });
  },

  getCompetitors: async (auditId) => {
    return await apiClient.get(`/api/audits/${auditId}/competitors`);
  },

  getCompetitorsComparison: async (auditId) => {
    return await apiClient.get(`/api/audits/${auditId}/competitors/comparison`);
  },
};
