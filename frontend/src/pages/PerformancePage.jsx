import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  Zap, ArrowLeft, AlertCircle, CheckCircle, AlertTriangle,
  Clock, HardDrive, Image, Shield, Server, Globe,
  Info, TrendingUp, BarChart2,
} from 'lucide-react';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import EmptyState from '../components/ui/EmptyState';
import { performanceApi } from '../api/performance';
import { auditsApi } from '../api/audits';
import './PerformancePage.css';

// ── Helpers ────────────────────────────────────────────────────────────────

function scoreClass(score) {
  if (score === null || score === undefined) return '';
  if (score >= 80) return 'perf-stat-card__value--good';
  if (score >= 50) return 'perf-stat-card__value--medium';
  return 'perf-stat-card__value--poor';
}

function fmtBytes(bytes) {
  if (!bytes && bytes !== 0) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function fmtMs(ms) {
  if (ms === null || ms === undefined) return '—';
  return `${ms}ms`;
}

function rtClass(ms) {
  if (ms === null || ms === undefined) return 'metric-chip--na';
  if (ms <= 200) return 'metric-chip--good';
  if (ms <= 500) return 'metric-chip--medium';
  return 'metric-chip--poor';
}

function psClass(score) {
  if (score === null || score === undefined) return 'metric-chip--na';
  if (score >= 80) return 'metric-chip--good';
  if (score >= 50) return 'metric-chip--medium';
  return 'metric-chip--poor';
}

const SEVERITY_ORDER = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };

function sortIssues(issues) {
  return [...issues].sort(
    (a, b) => (SEVERITY_ORDER[a.severity] ?? 4) - (SEVERITY_ORDER[b.severity] ?? 4)
  );
}

// ── CWV Card ───────────────────────────────────────────────────────────────

const CWV_INFO = {
  LCP: {
    label: 'LCP',
    full: 'Largest Contentful Paint',
    desc: 'Measures when the largest visible content element (image or text) is rendered.',
    goodVal: '≤ 2.5s',
    tool: 'Google PageSpeed Insights',
  },
  INP: {
    label: 'INP',
    full: 'Interaction to Next Paint',
    desc: 'Measures responsiveness — how quickly the page responds to user interactions.',
    goodVal: '≤ 200ms',
    tool: 'Google Search Console',
  },
  CLS: {
    label: 'CLS',
    full: 'Cumulative Layout Shift',
    desc: 'Measures visual stability — how much elements unexpectedly move during load.',
    goodVal: '≤ 0.1',
    tool: 'Lighthouse',
  },
};

function CWVCard({ metric }) {
  const info = CWV_INFO[metric];
  return (
    <Card className="perf-cwv-card">
      <div className="perf-cwv-card__metric">{info.label}</div>
      <div className="perf-cwv-card__status perf-cwv-card__status--unavailable">
        Not Measured
      </div>
      <div className="perf-cwv-card__desc">
        <strong>{info.full}:</strong> {info.desc}
        <br />
        <em>Good threshold: {info.goodVal}</em>
        <br />
        <em>Measure with: {info.tool}</em>
      </div>
    </Card>
  );
}

// ── Category breakdown ─────────────────────────────────────────────────────

const CATEGORY_ICONS = {
  server_response: <Server size={14} />,
  document_size:   <HardDrive size={14} />,
  images:          <Image size={14} />,
  compression:     <TrendingUp size={14} />,
  caching:         <Clock size={14} />,
  security:        <Shield size={14} />,
  mobile:          <Globe size={14} />,
};

function ScoreCategories({ categories }) {
  return (
    <div className="perf-categories-grid">
      {Object.entries(categories).map(([key, cat]) => (
        <div key={key} className="perf-category-item">
          <span className="perf-category-item__label">
            {CATEGORY_ICONS[key]}
            {cat.label}
          </span>
          <span
            className={`perf-category-item__count ${
              cat.issues > 0 ? 'perf-category-item__count--issues' : 'perf-category-item__count--ok'
            }`}
          >
            {cat.issues > 0 ? `${cat.issues} issue${cat.issues > 1 ? 's' : ''}` : '✓'}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Issue Item ─────────────────────────────────────────────────────────────

function IssueItem({ issue }) {
  const severityVariant = {
    CRITICAL: 'critical',
    HIGH: 'danger',
    MEDIUM: 'warning',
    LOW: 'info',
  }[issue.severity] || 'neutral';

  return (
    <Card className={`perf-issue-item perf-issue-item--${issue.severity}`} padding="none">
      <div className="perf-issue-item__header">
        <div className="perf-issue-item__title">{issue.title}</div>
        <Badge variant={severityVariant}>{issue.severity}</Badge>
      </div>
      {issue.page_url && (
        <div className="perf-issue-item__url">📄 {issue.page_url}</div>
      )}
      <div className="perf-issue-item__desc">{issue.description}</div>
      <div className="perf-issue-item__rec">
        <strong>Recommendation:</strong> {issue.recommendation_summary}
      </div>
    </Card>
  );
}

// ── Main ───────────────────────────────────────────────────────────────────

export default function PerformancePage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [audit, setAudit] = useState(null);
  const [perf, setPerf] = useState(null);
  const [pages, setPages] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [auditData, perfData, pagesData] = await Promise.all([
        auditsApi.getAudit(id),
        performanceApi.getAuditPerformance(id),
        performanceApi.getPagesPerformance(id).catch(() => []),
      ]);
      setAudit(auditData);
      setPerf(perfData);
      setPages(pagesData);
    } catch (err) {
      setError(err.message || 'Failed to load performance data.');
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  // ── States ──────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="loading-view">
        <div className="loading-spinner" />
        <div className="loading-text">Loading performance data…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="perf-page">
        <Card>
          <EmptyState
            icon={<AlertCircle size={32} />}
            title="Error"
            description={error}
            actions={
              <Button onClick={() => navigate(`/audit/${id}`)} variant="secondary">
                <ArrowLeft size={14} /> Back to Audit
              </Button>
            }
          />
        </Card>
      </div>
    );
  }

  if (!audit || audit.status !== 'completed') {
    const statusMsg = audit
      ? `Audit is currently "${audit.status}". Performance data will be available once the audit completes.`
      : 'Audit not found.';
    return (
      <div className="perf-page">
        <Button variant="outline" onClick={() => navigate(`/audit/${id}`)} className="mb-4">
          <ArrowLeft size={14} /> Back to Audit
        </Button>
        <Card>
          <EmptyState
            icon={<AlertTriangle size={32} />}
            title="Performance Not Available"
            description={statusMsg}
            actions={
              <Button onClick={() => navigate(`/audit/${id}`)} variant="primary">
                View Audit Status
              </Button>
            }
          />
        </Card>
      </div>
    );
  }

  if (!perf) {
    return (
      <div className="perf-page">
        <Card>
          <EmptyState
            icon={<Zap size={32} />}
            title="No Performance Data"
            description="Performance analysis was not collected for this audit. Re-run the audit to generate performance metrics."
          />
        </Card>
      </div>
    );
  }

  const sortedIssues = sortIssues(perf.performance_issues || []);

  return (
    <div className="perf-page">
      {/* Header */}
      <div className="perf-header">
        <div>
          <h1 className="perf-header__title">
            <Zap size={22} /> Performance Analysis
          </h1>
          <div className="perf-header__url">{audit.url}</div>
        </div>
        <Button variant="outline" size="sm" onClick={() => navigate(`/audit/${id}`)}>
          <ArrowLeft size={14} /> Back to Audit
        </Button>
      </div>

      {/* Overview cards */}
      <section>
        <h2 className="audit-result__section-title"><TrendingUp size={18} /> Overview</h2>
        <div className="perf-overview-grid">
          <Card className="perf-stat-card">
            <div className="perf-stat-card__label"><Zap size={12} /> Performance Score</div>
            <div className={`perf-stat-card__value ${scoreClass(perf.performance_score)}`}>
              {perf.performance_score !== null ? `${perf.performance_score}` : '—'}
            </div>
            <div className="perf-stat-card__note">Out of 100 (server-side measured)</div>
          </Card>

          <Card className="perf-stat-card">
            <div className="perf-stat-card__label"><Server size={12} /> Avg Response Time</div>
            <div className={`perf-stat-card__value ${
              perf.avg_response_time_ms !== null
                ? perf.avg_response_time_ms <= 200 ? 'perf-stat-card__value--good'
                  : perf.avg_response_time_ms <= 500 ? 'perf-stat-card__value--medium'
                  : 'perf-stat-card__value--poor'
                : ''
            }`}>
              {fmtMs(perf.avg_response_time_ms)}
            </div>
            <div className="perf-stat-card__note">Target: &lt; 200ms</div>
          </Card>

          <Card className="perf-stat-card">
            <div className="perf-stat-card__label"><HardDrive size={12} /> Total HTML Size</div>
            <div className="perf-stat-card__value">
              {fmtBytes(perf.total_html_size_bytes)}
            </div>
            <div className="perf-stat-card__note">Across {perf.pages_analyzed} pages</div>
          </Card>

          <Card className="perf-stat-card">
            <div className="perf-stat-card__label"><AlertTriangle size={12} /> Opportunities</div>
            <div className={`perf-stat-card__value ${
              perf.opportunities_count === 0 ? 'perf-stat-card__value--good'
                : perf.opportunities_count <= 3 ? 'perf-stat-card__value--medium'
                : 'perf-stat-card__value--poor'
            }`}>
              {perf.opportunities_count}
            </div>
            <div className="perf-stat-card__note">Across {perf.pages_count} pages</div>
          </Card>
        </div>
      </section>

      {/* Core Web Vitals */}
      <section>
        <h2 className="audit-result__section-title">
          <Globe size={18} /> Core Web Vitals
        </h2>
        <div className="perf-cwv-grid">
          <CWVCard metric="LCP" />
          <CWVCard metric="INP" />
          <CWVCard metric="CLS" />
        </div>
        <div className="perf-cwv-note">
          <Info size={12} style={{ display: 'inline', marginRight: 4 }} />
          {perf.cwv_note}
        </div>
      </section>

      {/* Category Breakdown */}
      {perf.score_categories && (
        <section>
          <h2 className="audit-result__section-title">
            <BarChart2 size={18} /> Category Breakdown
          </h2>
          <Card>
            <ScoreCategories categories={perf.score_categories} />
          </Card>
        </section>
      )}

      {/* Performance Issues */}
      <section>
        <h2 className="audit-result__section-title">
          <AlertCircle size={18} /> Performance Opportunities ({sortedIssues.length})
        </h2>
        {sortedIssues.length === 0 ? (
          <Card>
            <EmptyState
              icon={<CheckCircle size={32} />}
              title="No Issues Found"
              description="No performance issues were detected on the crawled pages."
            />
          </Card>
        ) : (
          <div className="perf-issue-list">
            {sortedIssues.map((issue, idx) => (
              <IssueItem key={issue.id || idx} issue={issue} />
            ))}
          </div>
        )}
      </section>

      {/* Page-level performance */}
      {pages.length > 0 && (
        <section>
          <h2 className="audit-result__section-title">
            <Globe size={18} /> Page-level Performance
          </h2>
          <Card>
            <div style={{ overflowX: 'auto' }}>
              <table className="perf-pages-table">
                <thead>
                  <tr>
                    <th>URL</th>
                    <th>Score</th>
                    <th>Response Time</th>
                    <th>HTML Size</th>
                    <th>Compressed</th>
                    <th>Cache</th>
                    <th>LCP</th>
                    <th>INP</th>
                    <th>CLS</th>
                  </tr>
                </thead>
                <tbody>
                  {pages.map((page) => (
                    <tr key={page.page_id}>
                      <td className="url-cell" title={page.url}>
                        {page.url.length > 50 ? `...${page.url.slice(-47)}` : page.url}
                      </td>
                      <td>
                        <span className={`metric-chip ${psClass(page.performance_score)}`}>
                          {page.performance_score !== null ? page.performance_score : '—'}
                        </span>
                      </td>
                      <td>
                        <span className={`metric-chip ${rtClass(page.response_time_ms)}`}>
                          {fmtMs(page.response_time_ms)}
                        </span>
                      </td>
                      <td>{fmtBytes(page.html_size_bytes)}</td>
                      <td>
                        {page.is_compressed
                          ? <CheckCircle size={14} color="var(--color-success-600, #16a34a)" />
                          : <AlertCircle size={14} color="var(--sev-high, #ea580c)" />}
                      </td>
                      <td>
                        {page.has_cache_control
                          ? <CheckCircle size={14} color="var(--color-success-600, #16a34a)" />
                          : <AlertCircle size={14} color="var(--sev-medium, #ca8a04)" />}
                      </td>
                      <td><span className="metric-chip metric-chip--na">—</span></td>
                      <td><span className="metric-chip metric-chip--na">—</span></td>
                      <td><span className="metric-chip metric-chip--na">—</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </section>
      )}
    </div>
  );
}
