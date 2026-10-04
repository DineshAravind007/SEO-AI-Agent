import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { History, PlusCircle, ExternalLink, RefreshCw, AlertCircle } from 'lucide-react';
import { auditsApi } from '../api/audits';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import EmptyState from '../components/ui/EmptyState';
import './AuditHistoryPage.css';

/* ── Helpers ──────────────────────────────────── */
function scoreClass(grade) {
  if (!grade) return 'none';
  const g = grade.toUpperCase();
  if (g === 'EXCELLENT') return 'excellent';
  if (g === 'GOOD') return 'good';
  if (g === 'FAIR') return 'fair';
  return 'poor';
}

function formatDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch (_) { return iso; }
}

/* ── Skeleton rows while loading ─────────────── */
function SkeletonRows({ count = 5 }) {
  return Array.from({ length: count }).map((_, i) => (
    <tr key={i} className="skeleton-row">
      {[240, 60, 80, 100, 80, 90].map((w, j) => (
        <td key={j}><div className="skeleton-cell" style={{ width: `${w}px` }} /></td>
      ))}
    </tr>
  ));
}

/* ── Status badge ────────────────────────────── */
function StatusBadge({ status }) {
  const map = {
    completed: 'success',
    failed:    'critical',
    crawling:  'info',
    analyzing: 'info',
    pending:   'neutral',
  };
  return <Badge variant={map[status] ?? 'neutral'}>{status}</Badge>;
}

/* ── Main component ──────────────────────────── */
export default function AuditHistoryPage() {
  const [audits, setAudits] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAudits = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await auditsApi.getAudits();
      setAudits(data.audits || []);
    } catch (err) {
      setError(err.message || 'Failed to load audit history.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchAudits(); }, [fetchAudits]);

  return (
    <div className="history-page">
      {/* Header */}
      <div className="history-page__header">
        <div>
          <h2 className="history-page__title">Audit History</h2>
          <p className="history-page__subtitle">
            All SEO audits you have run, newest first.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchAudits}
            icon={<RefreshCw size={14} strokeWidth={2} />}
            disabled={isLoading}
          >
            Refresh
          </Button>
          <Button
            as={Link}
            to="/audit/new"
            variant="primary"
            size="sm"
            icon={<PlusCircle size={14} strokeWidth={2} />}
          >
            New Audit
          </Button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <Card>
          <EmptyState
            icon={<AlertCircle size={24} strokeWidth={1.5} color="var(--color-error-600)" />}
            title="Could not load audit history"
            description={error}
            actions={
              <Button variant="secondary" onClick={fetchAudits} icon={<RefreshCw size={14} />}>
                Retry
              </Button>
            }
          />
        </Card>
      )}

      {/* Table */}
      {!error && (
        <Card padding="none">
          <div className="audit-table-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Website</th>
                  <th>Score</th>
                  <th>Grade</th>
                  <th>Status</th>
                  <th>Issues</th>
                  <th>Date</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <SkeletonRows count={5} />
                ) : audits.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={{ padding: 0, border: 'none' }}>
                      <EmptyState
                        icon={<History size={22} strokeWidth={1.5} />}
                        title="No audits yet"
                        description="Start your first SEO audit to see results here."
                        actions={
                          <Button
                            as={Link}
                            to="/audit/new"
                            variant="primary"
                            icon={<PlusCircle size={14} strokeWidth={2} />}
                          >
                            Start New Audit
                          </Button>
                        }
                      />
                    </td>
                  </tr>
                ) : (
                  audits.map(audit => (
                    <tr key={audit.id}>
                      <td>
                        <div className="audit-table__url" title={audit.url}>
                          {audit.url}
                        </div>
                        <div className="audit-table__meta">ID #{audit.id} · {audit.page_count} pages</div>
                      </td>
                      <td>
                        {audit.score != null ? (
                          <span className={`audit-table__score audit-table__score--${scoreClass(audit.grade)}`}>
                            {audit.score}
                          </span>
                        ) : (
                          <span className="audit-table__score audit-table__score--none">—</span>
                        )}
                      </td>
                      <td>
                        {audit.grade ? (
                          <span style={{ fontSize: 'var(--font-size-sm)', fontWeight: 'var(--font-weight-medium)', color: 'var(--color-text-secondary)' }}>
                            {audit.grade}
                          </span>
                        ) : '—'}
                      </td>
                      <td><StatusBadge status={audit.status} /></td>
                      <td>
                        <span style={{ fontSize: 'var(--font-size-sm)', color: audit.issue_count > 0 ? 'var(--sev-high)' : 'var(--color-success-600)', fontWeight: 'var(--font-weight-medium)' }}>
                          {audit.issue_count ?? '—'}
                        </span>
                      </td>
                      <td>
                        <span className="audit-table__meta">{formatDate(audit.created_at)}</span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <Button
                          as={Link}
                          to={`/audit/${audit.id}`}
                          variant="secondary"
                          size="sm"
                          iconRight={<ExternalLink size={12} strokeWidth={2} />}
                        >
                          View
                        </Button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Summary when loaded */}
      {!isLoading && !error && audits.length > 0 && (
        <p style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', textAlign: 'right' }}>
          Showing {audits.length} audit{audits.length !== 1 ? 's' : ''}
        </p>
      )}
    </div>
  );
}
