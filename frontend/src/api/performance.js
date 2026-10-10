import { apiClient } from './client';

export const performanceApi = {
  getAuditPerformance: (auditId) => apiClient.get(`/api/audits/${auditId}/performance`),
  getPagesPerformance: (auditId) => apiClient.get(`/api/audits/${auditId}/pages-performance`),
};
