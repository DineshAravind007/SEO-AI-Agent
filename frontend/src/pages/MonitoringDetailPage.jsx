import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, TrendingUp, TrendingDown, RefreshCw, Download,
  Activity, Clock, Calendar, Globe, BarChart2, CheckCircle, AlertCircle,
} from 'lucide-react';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Badge from '../components/ui/Badge';
import { monitoringApi } from '../api/monitoring';
import './MonitoringDetailPage.css';

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmt(dateStr) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString(undefined, {
    month: 'short', day: 'numeric', year: 'numeric',
  });
}

function fmtFull(dateStr) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleString(undefined, {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function ScoreCircle({ score }) {
  let color = '#6b7280';
  if (score >= 80) color = '#16a34a';
  else if (score >= 60) color = '#d97706';
  else if (score !== null && score !== undefined) color = '#dc2626';

  return (
    <div className="md-score-circle" style={{ borderColor: color }}>
      <span className="md-score-num" style={{ color }}>
        {score !== null && score !== undefined ? score : '—'}
      </span>
      <span className="md-score-denom">/100</span>
    </div>
  );
}

const CHART_COLORS = {
  score: 'var(--color-accent, #6366f1)',
  critical: 'var(--sev-critical, #dc2626)',
  high: 'var(--sev-high, #ea580c)',
  medium: 'var(--sev-medium, #ca8a04)',
  low: 'var(--sev-low, #2563eb)',
};

// ── Main component ────────────────────────────────────────────────────────────

export default function MonitoringDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [project, setProject] = useState(null);
  const [history, setHistory] = useState([]);
  const [changes, setChanges] = useState(null);
  const [reports, setReports] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isRunning, setIsRunning] = useState(false);
  const [runMessage, setRunMessage] = useState(null);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [projData, histData, changesData, reportsData] = await Promise.all([
        monitoringApi.getProject(id),
        monitoringApi.getHistory(id),
        monitoringApi.getChanges(id),
        monitoringApi.getReports(id),
      ]);
      setProject(projData);
      setHistory(histData);
      setChanges(changesData);
      setReports(reportsData);
    } catch (err) {
      setError(err.message || 'Failed to load project details');
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleRunNow = async () => {
    if (isRunning) return;
    setIsRunning(true);
    setRunMessage(null);
    try {
      await monitoringApi.runNow(id);
      setRunMessage('Audit triggered! Results will appear after the crawl completes.');
    } catch (err) {
      setRunMessage(`Error: ${err.message}`);
    } finally {
      setIsRunning(false);
    }
  };

  // ── Loading / error states ─────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="mon-detail">
        <div className="mon-detail__loading">
          <Activity size={32} className="mon-loading-icon" />
          <span>Loading project details…</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mon-detail">
        <div className="error-alert" role="alert">{error}</div>
        <Button variant="outline" onClick={() => navigate('/monitoring')}>
          <ArrowLeft size={14} /> Back to Monitoring
        </Button>
      </div>
    );
  }

  if (!project) return null;

  // ── Chart data ─────────────────────────────────────────────────────────────

  const scoreTrendData = history.map(h => ({
    date: fmt(h.date),
    Score: h.score,
    auditId: h.audit_id,
  }));

  const issueTrendData = history.map(h => ({
    date: fmt(h.date),
    Critical: h.critical_issues || 0,
    High: h.high_issues || 0,
    Medium: h.medium_issues || 0,
    Low: h.low_issues || 0,
  }));

  const hasHistory = history.length > 0;
  const latestChange = changes?.has_changes ? changes : null;

  return (
    <div className="mon-detail">

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="mon-detail__header">
        <Button variant="outline" onClick={() => navigate('/monitoring')} className="mon-back-btn">
          <ArrowLeft size={14} /> Back
        </Button>
        <div className="mon-detail__title-block">
          <h1 className="mon-detail__title">{project.name}</h1>
          <span className="mon-detail__subtitle">
            <Globe size={12} /> {project.url}
          </span>
        </div>
        <div className="mon-detail__header-actions">
          <Badge variant={project.is_active ? 'success' : 'neutral'}>
            {project.is_active ? 'Active' : 'Paused'}
          </Badge>
          {project.is_active && (
            <Button
              id="btn-run-now"
              variant="primary"
              onClick={handleRunNow}
              disabled={isRunning}
            >
              <RefreshCw size={14} className={isRunning ? 'spin' : ''} />
              {isRunning ? 'Running…' : 'Run Audit Now'}
            </Button>
          )}
        </div>
      </div>

      {runMessage && (
        <div
          className={`mon-run-msg ${runMessage.startsWith('Error') ? 'mon-run-msg--error' : 'mon-run-msg--ok'}`}
          role="status"
        >
          {runMessage}
        </div>
      )}

      {/* ── Meta cards ─────────────────────────────────────────────────── */}
      <div className="mon-meta-grid">
        <Card className="mon-meta-card">
          <span className="mon-meta-card__label"><BarChart2 size={12} /> Current Score</span>
          <ScoreCircle score={project.last_score} />
        </Card>
        <Card className="mon-meta-card">
          <span className="mon-meta-card__label"><TrendingUp size={12} /> Score Change</span>
          {latestChange ? (
            <div className={`mon-meta-card__change ${latestChange.score_change > 0 ? 'up' : latestChange.score_change < 0 ? 'down' : 'flat'}`}>
              {latestChange.score_change > 0 && <TrendingUp size={18} />}
              {latestChange.score_change < 0 && <TrendingDown size={18} />}
              {latestChange.score_change === 0 && '—'}
              {latestChange.score_change !== 0 && (
                <span>{latestChange.score_change > 0 ? '+' : ''}{latestChange.score_change}</span>
              )}
            </div>
          ) : <span className="mon-meta-card__empty">No changes yet</span>}
        </Card>
        <Card className="mon-meta-card">
          <span className="mon-meta-card__label"><Clock size={12} /> Last Audit</span>
          <span className="mon-meta-card__value">{fmt(project.last_audit_date)}</span>
        </Card>
        <Card className="mon-meta-card">
          <span className="mon-meta-card__label"><Calendar size={12} /> Next Audit</span>
          <span className="mon-meta-card__value">{fmt(project.next_audit_date)}</span>
        </Card>
        <Card className="mon-meta-card">
          <span className="mon-meta-card__label"><Activity size={12} /> Frequency</span>
          <span className="mon-meta-card__value" style={{ textTransform: 'capitalize' }}>
            {project.frequency}
          </span>
        </Card>
      </div>

      {/* ── Main content grid ───────────────────────────────────────────── */}
      <div className="mon-detail__grid">
        <div className="mon-detail__main">

          {/* Score Trend Chart */}
          <Card>
            <h2 className="card-title">SEO Score Trend</h2>
            <div className="chart-container">
              {hasHistory ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={scoreTrendData} margin={{ top: 8, right: 16, left: -16, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--color-border)" />
                    <XAxis
                      dataKey="date"
                      stroke="var(--color-text-secondary)"
                      fontSize={11}
                      tickLine={false}
                    />
                    <YAxis
                      domain={[0, 100]}
                      stroke="var(--color-text-secondary)"
                      fontSize={11}
                      tickLine={false}
                      axisLine={false}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'var(--color-surface)',
                        borderColor: 'var(--color-border)',
                        borderRadius: 'var(--radius-md)',
                        fontSize: '12px',
                      }}
                      itemStyle={{ color: 'var(--color-text-primary)' }}
                    />
                    <Line
                      type="monotone"
                      dataKey="Score"
                      stroke={CHART_COLORS.score}
                      strokeWidth={3}
                      dot={{ r: 4, fill: CHART_COLORS.score, strokeWidth: 0 }}
                      activeDot={{ r: 6 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="chart-empty">
                  <BarChart2 size={32} />
                  <p>No historical data yet.</p>
                  <p className="chart-empty__sub">Run your first audit to start tracking.</p>
                </div>
              )}
            </div>
          </Card>

          {/* Issue Trend Chart */}
          {hasHistory && (
            <Card>
              <h2 className="card-title">Issue Trend</h2>
              <div className="chart-container">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={issueTrendData} margin={{ top: 8, right: 16, left: -16, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--color-border)" />
                    <XAxis dataKey="date" stroke="var(--color-text-secondary)" fontSize={11} tickLine={false} />
                    <YAxis stroke="var(--color-text-secondary)" fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'var(--color-surface)',
                        borderColor: 'var(--color-border)',
                        borderRadius: 'var(--radius-md)',
                        fontSize: '12px',
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: '12px' }} />
                    <Bar dataKey="Critical" stackId="a" fill={CHART_COLORS.critical} />
                    <Bar dataKey="High" stackId="a" fill={CHART_COLORS.high} />
                    <Bar dataKey="Medium" stackId="a" fill={CHART_COLORS.medium} />
                    <Bar dataKey="Low" stackId="a" fill={CHART_COLORS.low} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          )}

          {/* Latest Changes */}
          {latestChange && (
            <Card>
              <h2 className="card-title">Latest Changes</h2>
              <div className="mon-changes-grid">
                <div className="mon-change-group">
                  <span className="mon-change-group__label">Score</span>
                  <div className="mon-change-group__val">
                    <span>{latestChange.score_old ?? '—'}</span>
                    <span className="mon-arrow">→</span>
                    <span className="font-bold">{latestChange.score_new ?? '—'}</span>
                    {latestChange.score_change > 0 && (
                      <span className="mon-delta mon-delta--up">+{latestChange.score_change}</span>
                    )}
                    {latestChange.score_change < 0 && (
                      <span className="mon-delta mon-delta--down">{latestChange.score_change}</span>
                    )}
                  </div>
                </div>
                <div className="mon-change-group">
                  <span className="mon-change-group__label">Critical Issues</span>
                  <div className="mon-change-group__val">
                    <span>{latestChange.critical_old ?? 0}</span>
                    <span className="mon-arrow">→</span>
                    <span className="font-bold">{latestChange.critical_new ?? 0}</span>
                  </div>
                </div>
                <div className="mon-change-group">
                  <span className="mon-change-group__label">High Issues</span>
                  <div className="mon-change-group__val">
                    <span>{latestChange.high_old ?? 0}</span>
                    <span className="mon-arrow">→</span>
                    <span className="font-bold">{latestChange.high_new ?? 0}</span>
                  </div>
                </div>
                <div className="mon-change-group">
                  <span className="mon-change-group__label">Pages Crawled</span>
                  <div className="mon-change-group__val">
                    <span>{latestChange.pages_old ?? 0}</span>
                    <span className="mon-arrow">→</span>
                    <span className="font-bold">{latestChange.pages_new ?? 0}</span>
                  </div>
                </div>
              </div>

              {/* Resolved issues */}
              {latestChange.resolved_issues?.length > 0 && (
                <div className="mon-issue-diff">
                  <h3 className="mon-issue-diff__title mon-issue-diff__title--ok">
                    <CheckCircle size={14} /> Resolved Issues ({latestChange.resolved_issues.length})
                  </h3>
                  <ul className="mon-issue-diff__list">
                    {latestChange.resolved_issues.map((issue, i) => (
                      <li key={i} className="mon-issue-diff__item mon-issue-diff__item--ok">
                        <span className="mon-issue-diff__code">{issue.code}</span>
                        {issue.title && <span>{issue.title}</span>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* New issues */}
              {latestChange.new_issues?.length > 0 && (
                <div className="mon-issue-diff">
                  <h3 className="mon-issue-diff__title mon-issue-diff__title--bad">
                    <AlertCircle size={14} /> New Issues ({latestChange.new_issues.length})
                  </h3>
                  <ul className="mon-issue-diff__list">
                    {latestChange.new_issues.map((issue, i) => (
                      <li key={i} className="mon-issue-diff__item mon-issue-diff__item--bad">
                        <span className="mon-issue-diff__code">{issue.code}</span>
                        {issue.title && <span>{issue.title}</span>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </Card>
          )}
        </div>

        {/* ── Sidebar ────────────────────────────────────────────────────── */}
        <div className="mon-detail__sidebar">
          <Card>
            <h2 className="card-title">Recent Audits</h2>
            <div className="mon-reports">
              {reports.length === 0 ? (
                <p className="mon-reports__empty">No audits yet. Run one to get started.</p>
              ) : (
                reports.map((r) => {
                  const changes = r.changes_data ? (() => {
                    try { return JSON.parse(r.changes_data); } catch { return null; }
                  })() : null;
                  const scoreNew = changes?.score_new;
                  const scoreChange = r.score_change;

                  return (
                    <div key={r.id} className="mon-report-item">
                      <div className="mon-report-item__main">
                        <div className="mon-report-item__date">
                          <Clock size={11} />
                          {fmtFull(r.created_at)}
                        </div>
                        <div className="mon-report-item__score">
                          {scoreNew !== undefined && scoreNew !== null && (
                            <span className="mon-report-item__score-val">Score: {scoreNew}</span>
                          )}
                          {scoreChange !== null && scoreChange !== undefined && (
                            <span className={`mon-report-item__delta ${scoreChange > 0 ? 'up' : scoreChange < 0 ? 'down' : 'flat'}`}>
                              {scoreChange > 0 ? '+' : ''}{scoreChange}
                            </span>
                          )}
                        </div>
                      </div>
                      <Button
                        id={`btn-download-${r.id}`}
                        variant="outline"
                        size="sm"
                        onClick={() => monitoringApi.downloadReport(r.audit_id)}
                        title="Download HTML Report"
                      >
                        <Download size={12} /> Report
                      </Button>
                    </div>
                  );
                })
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
