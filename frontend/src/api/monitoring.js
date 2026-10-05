import { apiClient } from './client';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const monitoringApi = {
  /** Create a new monitoring project */
  createProject: (data) =>
    apiClient.post('/api/monitoring', data),

  /** List all monitoring projects (augmented with last_score / score_change) */
  listProjects: () =>
    apiClient.get('/api/monitoring'),

  /** Get a single monitoring project by ID */
  getProject: (id) =>
    apiClient.get(`/api/monitoring/${id}`),

  /** Update name, frequency, is_active, max_pages, max_depth */
  updateProject: (id, data) =>
    apiClient.put(`/api/monitoring/${id}`, data),

  /** Delete a monitoring project */
  deleteProject: (id) =>
    apiClient.delete(`/api/monitoring/${id}`),

  /** Trigger a manual audit run (runs in background) */
  runNow: (id) =>
    apiClient.post(`/api/monitoring/${id}/run`, {}),

  /**
   * Get SEO score history for charting.
   * Returns [ { date, audit_id, score, critical_issues, high_issues,
   *             medium_issues, low_issues, page_count }, ... ]
   */
  getHistory: (id) =>
    apiClient.get(`/api/monitoring/${id}/history`),

  /**
   * Get the latest change summary (score delta, new/resolved issues).
   * Returns { has_changes, score_change, new_issues, resolved_issues, ... }
   */
  getChanges: (id) =>
    apiClient.get(`/api/monitoring/${id}/changes`),

  /**
   * Get all monitoring reports for a project (newest first).
   * Each report has audit_id, previous_audit_id, score_change, changes_data.
   */
  getReports: (id) =>
    apiClient.get(`/api/monitoring/${id}/reports`),

  /**
   * Download the HTML audit report for a specific audit.
   * Opens the report in a new tab.
   */
  downloadReport: (auditId) => {
    const url = `${BASE_URL}/api/audits/${auditId}/report`;
    window.open(url, '_blank');
  },

  /** Trigger the scheduler tick (for testing or manual invocation) */
  schedulerTick: () =>
    apiClient.post('/api/monitoring/scheduler/tick', {}),
};
