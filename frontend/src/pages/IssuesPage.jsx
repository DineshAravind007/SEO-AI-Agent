import { useState, useEffect, useMemo } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { AlertTriangle, PlusCircle, AlertCircle, RefreshCw } from 'lucide-react';
import { auditsApi } from '../api/audits';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import EmptyState from '../components/ui/EmptyState';
import './IssuesPage.css';

/* ── Severity ordering ──────────────────────── */
const SEVERITY_ORDER = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };

/* ── Filter button ──────────────────────────── */
function FilterBtn({ label, value, active, count, onClick }) {
  const cls = [
    'filter-btn',
    `filter-btn--${value.toLowerCase()}`,
    active ? 'filter-btn--active' : '',
  ].filter(Boolean).join(' ');

  return (
    <button type="button" className={cls} onClick={() => onClick(value)} aria-pressed={active}>
      {label} {count != null && `(${count})`}
    </button>
  );
}

/* ── Issue card ─────────────────────────────── */
function IssueCard({ issue }) {
  return (
    <Card className={`issue-card issue-card--${issue.severity}`} padding="sm">
      <div className="issue-card__top">
        <div className="issue-card__title">{issue.title}</div>
        <div className="issue-card__badges">
          <Badge severity={issue.severity} />
          <Badge variant="neutral">{issue.category}</Badge>
        </div>
      </div>

      <p className="issue-card__desc">{issue.description}</p>

      {issue.page_url && (
        <div className="issue-card__url">{issue.page_url}</div>
      )}

      <div className="issue-card__meta">
        {issue.impact && (
          <div className="issue-card__meta-row">
            <span className="issue-card__meta-label">Impact</span>
            <span className="issue-card__meta-value">{issue.impact}</span>
          </div>
        )}
        {issue.recommendation_summary && (
          <div className="issue-card__meta-row">
            <span className="issue-card__meta-label">Recommendation</span>
            <span className="issue-card__meta-value">{issue.recommendation_summary}</span>
          </div>
        )}
      </div>
    </Card>
  );
}

/* ── No audit selected — prompt ─────────────── */
function NoAuditPrompt() {
  return (
    <div className="issues-page">
      <div className="issues-page__header">
        <div>
          <h2 className="issues-page__title">Issues Explorer</h2>
          <p className="issues-page__subtitle">Detected SEO issues from your audits.</p>
        </div>
      </div>
      <Card>
        <EmptyState
          icon={<AlertTriangle size={22} strokeWidth={1.5} />}
          title="Select an audit to explore issues"
          description="Navigate to an audit result and click 'View Issues' to explore detected issues with severity filtering."
          actions={
            <>
              <Button as={Link} to="/audits" variant="secondary">View Audit History</Button>
              <Button as={Link} to="/audit/new" variant="primary" icon={<PlusCircle size={14} />}>New Audit</Button>
            </>
          }
        />
      </Card>
    </div>
  );
}

/* ── Main page ──────────────────────────────── */
export default function IssuesPage() {
  const [searchParams] = useSearchParams();
  const auditId = searchParams.get('auditId');

  const [issues, setIssues] = useState([]);
  const [auditUrl, setAuditUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [severityFilter, setSeverityFilter] = useState('ALL');
  const [categoryFilter, setCategoryFilter] = useState('ALL');

  useEffect(() => {
    if (!auditId) return;
    const load = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const [issuesRes, auditRes] = await Promise.all([
          auditsApi.getAuditIssues(auditId),
          auditsApi.getAudit(auditId),
        ]);
        const raw = (issuesRes.issues || []).slice().sort(
          (a, b) => (SEVERITY_ORDER[a.severity] ?? 99) - (SEVERITY_ORDER[b.severity] ?? 99)
        );
        setIssues(raw);
        setAuditUrl(auditRes.url || '');
      } catch (err) {
        setError(err.message || 'Failed to load issues.');
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, [auditId]);

  // Count by severity for filter badges
  const counts = useMemo(() => {
    const c = { ALL: issues.length, CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 };
    issues.forEach(i => { if (c[i.severity] != null) c[i.severity]++; });
    return c;
  }, [issues]);

  // Filter
  const filtered = useMemo(() => issues.filter(i => {
    const sevOk = severityFilter === 'ALL' || i.severity === severityFilter;
    const catOk = categoryFilter === 'ALL' || i.category === categoryFilter;
    return sevOk && catOk;
  }), [issues, severityFilter, categoryFilter]);

  const categories = useMemo(() => [...new Set(issues.map(i => i.category))], [issues]);

  if (!auditId) return <NoAuditPrompt />;

  return (
    <div className="issues-page">
      {/* Header */}
      <div className="issues-page__header">
        <div>
          <h2 className="issues-page__title">Issues Explorer</h2>
          <p className="issues-page__subtitle">
            {auditUrl ? auditUrl : `Audit #${auditId}`}
          </p>
        </div>
        <Button as={Link} to={`/audit/${auditId}`} variant="secondary" size="sm">
          ← Back to Audit
        </Button>
      </div>

      {/* Error */}
      {error && (
        <Card>
          <EmptyState
            icon={<AlertCircle size={22} strokeWidth={1.5} color="var(--color-error-600)" />}
            title="Could not load issues"
            description={error}
          />
        </Card>
      )}

      {/* Loading */}
      {isLoading && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', color: 'var(--color-text-secondary)' }}>
          <RefreshCw size={16} style={{ animation: 'spin 1s linear infinite' }} />
          Loading issues...
        </div>
      )}

      {/* Content */}
      {!isLoading && !error && (
        <>
          {/* Filter bar */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-4)', alignItems: 'center' }}>
            <div className="filter-bar" role="group" aria-label="Filter by severity">
              {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(sev => (
                <FilterBtn
                  key={sev}
                  label={sev === 'ALL' ? 'All Severities' : sev}
                  value={sev}
                  active={severityFilter === sev}
                  count={sev !== 'ALL' ? counts[sev] : counts.ALL}
                  onClick={setSeverityFilter}
                />
              ))}
            </div>

            {categories.length > 1 && (
              <div className="filter-bar" role="group" aria-label="Filter by category">
                <FilterBtn label="All Categories" value="ALL" active={categoryFilter === 'ALL'} onClick={setCategoryFilter} />
                {categories.map(cat => (
                  <FilterBtn key={cat} label={cat} value={cat} active={categoryFilter === cat} onClick={setCategoryFilter} />
                ))}
              </div>
            )}
          </div>

          {/* Results count */}
          <span className="issues-count">
            {filtered.length} issue{filtered.length !== 1 ? 's' : ''} shown
            {filtered.length < issues.length && ` of ${issues.length}`}
          </span>

          {/* Issues list */}
          {filtered.length === 0 ? (
            <Card>
              <EmptyState
                icon={<AlertTriangle size={22} strokeWidth={1.5} />}
                title={issues.length === 0 ? 'No issues detected' : 'No issues match this filter'}
                description={
                  issues.length === 0
                    ? 'Great news — no SEO issues were detected for this audit.'
                    : 'Try a different severity or category filter.'
                }
                actions={issues.length > 0 && (
                  <Button variant="secondary" onClick={() => { setSeverityFilter('ALL'); setCategoryFilter('ALL'); }}>
                    Clear Filters
                  </Button>
                )}
              />
            </Card>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
              {filtered.map(issue => <IssueCard key={issue.id} issue={issue} />)}
            </div>
          )}
        </>
      )}
    </div>
  );
}
