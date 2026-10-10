import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { 
  AlertCircle, CheckCircle, Activity, 
  AlertTriangle, RefreshCw, FileText, Download, BarChart2, Zap
} from 'lucide-react';
import { auditsApi } from '../api/audits';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import EmptyState from '../components/ui/EmptyState';
import './AuditResultPage.css';
import '../components/ui/Form.css';

const STATUS_MESSAGES = {
  pending: "Preparing audit...",
  crawling: "Crawling website...",
  analyzing: "Analyzing SEO factors...",
};

function getScoreGradeClass(grade) {
  if (!grade) return '';
  const g = grade.toUpperCase();
  if (g === 'EXCELLENT') return 'score--excellent';
  if (g === 'GOOD') return 'score--good';
  if (g === 'FAIR') return 'score--fair';
  // 'Needs Improvement', 'Critical', or any other failing grade
  return 'score--poor';
}

export default function AuditResultPage() {
  const { id } = useParams();
  
  const [audit, setAudit] = useState(null);
  const [scoreData, setScoreData] = useState(null);
  const [issues, setIssues] = useState([]);
  const [pages, setPages] = useState([]);
  
  const [error, setError] = useState(null);
  const [isPolling, setIsPolling] = useState(true);
  const [isLoadingResults, setIsLoadingResults] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState(null);

  const handleDownloadReport = async () => {
    setIsDownloading(true);
    setDownloadError(null);
    try {
      await auditsApi.downloadAuditReport(id);
    } catch (err) {
      setDownloadError(err.message || 'Failed to generate report.');
    } finally {
      setIsDownloading(false);
    }
  };

  // Poll for audit status
  useEffect(() => {
    let timeoutId;
    
    const fetchStatus = async () => {
      try {
        const data = await auditsApi.getAudit(id);
        setAudit(data);
        
        if (['pending', 'crawling', 'analyzing'].includes(data.status)) {
          // Continue polling
          timeoutId = setTimeout(fetchStatus, 2000);
        } else {
          setIsPolling(false);
        }
      } catch (err) {
        setError(err.message || 'Failed to fetch audit status.');
        setIsPolling(false);
      }
    };
    
    fetchStatus();
    
    return () => clearTimeout(timeoutId);
  }, [id]);

  // Fetch results when completed
  useEffect(() => {
    if (audit?.status === 'completed') {
      const fetchResults = async () => {
        setIsLoadingResults(true);
        try {
          const [scoreRes, issuesRes, pagesRes] = await Promise.all([
            auditsApi.getAuditScore(id).catch(() => null), // Catch if not scored yet
            auditsApi.getAuditIssues(id),
            auditsApi.getAuditPages(id)
          ]);
          
          if (scoreRes) setScoreData(scoreRes);
          if (issuesRes) setIssues(issuesRes.issues || []);
          if (pagesRes) setPages(pagesRes.pages || []);
          
        } catch (err) {
          setError(err.message || 'Failed to load audit results.');
        } finally {
          setIsLoadingResults(false);
        }
      };
      
      fetchResults();
    }
  }, [audit?.status, id]);

  if (error) {
    return (
      <div className="audit-result">
        <Card>
          <EmptyState
            icon={<AlertCircle size={32} strokeWidth={1.5} color="var(--color-error-600)" />}
            title="Error Loading Audit"
            description={error}
            actions={
              <Button as={Link} to="/dashboard" variant="secondary">
                Back to Dashboard
              </Button>
            }
          />
        </Card>
      </div>
    );
  }

  if (!audit) {
    return (
      <div className="loading-view">
        <div className="loading-spinner" />
        <div className="loading-text">Loading audit...</div>
      </div>
    );
  }

  if (audit.status === 'failed') {
    return (
      <div className="audit-result">
        <div className="audit-result__header">
          <div className="audit-result__url-group">
            <h1 className="audit-result__url">{audit.url}</h1>
            <div className="audit-result__meta">
              <Badge variant="critical">Failed</Badge>
              <span>Audit #{audit.id}</span>
            </div>
          </div>
        </div>
        <Card>
          <EmptyState
            icon={<AlertCircle size={32} strokeWidth={1.5} color="var(--color-error-600)" />}
            title="Audit Failed"
            description={audit.error_message || "An unknown error occurred during the audit."}
            actions={
              <Button as={Link} to="/audit/new" variant="primary">
                Try Again
              </Button>
            }
          />
        </Card>
      </div>
    );
  }

  if (isPolling) {
    return (
      <div className="loading-view">
        <div className="loading-spinner" />
        <div className="loading-text">{STATUS_MESSAGES[audit.status] || "Processing..."}</div>
        <div className="loading-subtext">This may take a few moments. We are analyzing {audit.url}.</div>
      </div>
    );
  }

  // COMPLETED STATE
  return (
    <div className="audit-result">
      
      {/* Header */}
      <div className="audit-result__header">
        <div className="audit-result__header-top">
          <div className="audit-result__url-group">
            <h1 className="audit-result__url">{audit.url}</h1>
            <div className="audit-result__meta">
              <Badge variant="success">Completed</Badge>
              <span>Audit #{audit.id}</span>
              <span>•</span>
              <span>Crawled {pages.length} pages</span>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
            <Button
              variant="secondary"
              size="sm"
              onClick={handleDownloadReport}
              loading={isDownloading}
              icon={<Download size={14} strokeWidth={2} />}
            >
              Download Report
            </Button>
            <Button as={Link} to={`/audit/${audit.id}/competitors`} variant="secondary" size="sm" icon={<BarChart2 size={14} />}>
              Compare
            </Button>
            <Button as={Link} to={`/audit/${audit.id}/performance`} variant="secondary" size="sm" icon={<Zap size={14} />}>
              Performance
            </Button>
            <Button as={Link} to={`/issues?auditId=${audit.id}`} variant="secondary" size="sm" icon={<AlertTriangle size={14} />}>
              View Issues
            </Button>
            <Button as={Link} to={`/audit/${audit.id}/recommendations`} variant="primary" size="sm" icon={<RefreshCw size={14} />}>
              AI Recommendations
            </Button>
          </div>
        </div>
        {downloadError && (
          <div className="error-alert" role="alert" style={{ marginTop: 'var(--space-3)' }}>
            <AlertCircle size={14} style={{ display: 'inline', marginRight: 6 }} />
            {downloadError}
          </div>
        )}
      </div>

      {isLoadingResults ? (
        <div className="loading-view">
          <div className="loading-spinner" />
          <div className="loading-text">Loading results...</div>
        </div>
      ) : (
        <>
          {/* Score Section */}
          {scoreData && (
            <section>
              <h2 className="audit-result__section-title">
                <Activity size={20} /> SEO Health Score
              </h2>
              <div className="audit-result__score-grid">
                <div className={`score-display ${getScoreGradeClass(scoreData.grade)}`}>
                  <div className="score-display__value">{scoreData.score}/100</div>
                  <div className="score-display__grade">Grade: {scoreData.grade}</div>
                </div>
                <Card>
                  <div style={{ marginBottom: 'var(--space-4)' }}>
                    <h3 style={{ fontSize: 'var(--font-size-md)', marginBottom: 'var(--space-2)' }}>Severity Breakdown</h3>
                    <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)' }}>
                      {scoreData.explanation}
                    </p>
                  </div>
                  <div className="severity-breakdown">
                    <div className="severity-item" style={{ borderLeft: '4px solid var(--sev-critical)'}}>
                      <div className="severity-item__label">Critical</div>
                      <div className="severity-item__count" style={{ color: 'var(--sev-critical)'}}>{scoreData.severity_counts?.CRITICAL || 0}</div>
                    </div>
                    <div className="severity-item" style={{ borderLeft: '4px solid var(--sev-high)'}}>
                      <div className="severity-item__label">High</div>
                      <div className="severity-item__count" style={{ color: 'var(--sev-high)'}}>{scoreData.severity_counts?.HIGH || 0}</div>
                    </div>
                    <div className="severity-item" style={{ borderLeft: '4px solid var(--sev-medium)'}}>
                      <div className="severity-item__label">Medium</div>
                      <div className="severity-item__count" style={{ color: 'var(--sev-medium)'}}>{scoreData.severity_counts?.MEDIUM || 0}</div>
                    </div>
                    <div className="severity-item" style={{ borderLeft: '4px solid var(--sev-low)'}}>
                      <div className="severity-item__label">Low</div>
                      <div className="severity-item__count" style={{ color: 'var(--sev-low)'}}>{scoreData.severity_counts?.LOW || 0}</div>
                    </div>
                  </div>
                </Card>
              </div>
            </section>
          )}

          {/* Issues Section */}
          <section>
            <h2 className="audit-result__section-title">
              <AlertTriangle size={20} /> Detected Issues ({issues.length})
            </h2>
            {issues.length === 0 ? (
              <Card>
                <EmptyState
                  icon={<CheckCircle size={32} color="var(--color-success-500)" />}
                  title="No Issues Found"
                  description="Great job! Your website looks healthy based on our checks."
                />
              </Card>
            ) : (
              <div className="issue-list">
                {issues.map(issue => (
                  <Card key={issue.id} className={`issue-item issue-item--${issue.severity}`} padding="sm">
                    <div className="issue-item__title">{issue.title}</div>
                    <div className="issue-item__desc">{issue.description}</div>
                    <div className="issue-item__meta">
                      <Badge severity={issue.severity} />
                      <span>{issue.category}</span>
                      <span className="truncate" style={{ maxWidth: '300px' }}>{issue.page_url}</span>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </section>
          
          {/* Pages Section */}
          <section>
            <h2 className="audit-result__section-title">
              <FileText size={20} /> Crawled Pages ({pages.length})
            </h2>
            <Card padding="none">
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse', fontSize: 'var(--font-size-sm)' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--color-border)', backgroundColor: 'var(--color-neutral-50)' }}>
                      <th style={{ padding: 'var(--space-3) var(--space-4)' }}>URL</th>
                      <th style={{ padding: 'var(--space-3) var(--space-4)' }}>Status</th>
                      <th style={{ padding: 'var(--space-3) var(--space-4)' }}>Title</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pages.slice(0, 10).map(page => (
                      <tr key={page.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                        <td style={{ padding: 'var(--space-3) var(--space-4)', maxWidth: '250px' }} className="truncate">
                          {page.url}
                        </td>
                        <td style={{ padding: 'var(--space-3) var(--space-4)' }}>
                          {page.status_code === 200 ? 
                            <span style={{ color: 'var(--color-success-600)'}}>{page.status_code}</span> : 
                            <span style={{ color: 'var(--color-error-600)'}}>{page.status_code || page.crawl_status}</span>
                          }
                        </td>
                        <td style={{ padding: 'var(--space-3) var(--space-4)', maxWidth: '250px' }} className="truncate">
                          {page.title || '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {pages.length > 10 && (
                <div style={{ padding: 'var(--space-3) var(--space-4)', textAlign: 'center', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-secondary)' }}>
                  Showing first 10 pages out of {pages.length}
                </div>
              )}
            </Card>
          </section>
        </>
      )}
    </div>
  );
}
