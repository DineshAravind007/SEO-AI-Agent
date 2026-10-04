import { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { RefreshCw, PlusCircle, AlertCircle, BarChart2, AlertTriangle, ArrowRight, CheckCircle, ExternalLink } from 'lucide-react';
import { auditsApi } from '../api/audits';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import EmptyState from '../components/ui/EmptyState';
import './CompetitorsPage.css';

function CompScoreCard({ title, score, grade }) {
  const g = (grade || '').toUpperCase();
  let cls = 'none';
  if (g === 'EXCELLENT' || g === 'GOOD') cls = 'excellent';
  if (g === 'FAIR') cls = 'fair';
  if (g === 'NEEDS IMPROVEMENT' || g === 'POOR') cls = 'poor';

  return (
    <Card className="comp-score-card">
      <div className="comp-score-card__title">{title}</div>
      <div className="comp-score-card__body">
        {score != null ? (
          <div className={`comp-score-card__score comp-score-card__score--${cls}`}>
            {score}
          </div>
        ) : (
          <div className="comp-score-card__score comp-score-card__score--none">—</div>
        )}
        {grade && <div className="comp-score-card__grade">{grade}</div>}
      </div>
    </Card>
  );
}

export default function CompetitorsPage() {
  const { id } = useParams();
  
  const [baseAudit, setBaseAudit] = useState(null);
  const [competitors, setCompetitors] = useState([]);
  const [comparison, setComparison] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isComparing, setIsComparing] = useState(false);
  const [error, setError] = useState(null);

  // Form states
  const [showForm, setShowForm] = useState(false);
  const [newUrls, setNewUrls] = useState(['', '', '']);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [auditRes, compRes] = await Promise.all([
        auditsApi.getAudit(id),
        auditsApi.getCompetitors(id)
      ]);
      setBaseAudit(auditRes);
      setCompetitors(compRes || []);
      
      const allDone = compRes.length > 0 && compRes.every(c => c.competitor_audit.status === 'completed' || c.competitor_audit.status === 'failed');
      
      if (allDone && auditRes.status === 'completed') {
        setIsComparing(true);
        try {
          const compData = await auditsApi.getCompetitorsComparison(id);
          setComparison(compData);
        } catch (err) {
          // It's ok if comparison fails if no competitors are completed successfully
        } finally {
          setIsComparing(false);
        }
      }
    } catch (err) {
      setError(err.message || 'Failed to load competitors.');
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Poll if any competitor is pending/crawling/analyzing
  useEffect(() => {
    const isPolling = competitors.some(c => 
      ['pending', 'crawling', 'analyzing'].includes(c.competitor_audit.status)
    );
    
    if (isPolling) {
      const interval = setInterval(loadData, 3000);
      return () => clearInterval(interval);
    }
  }, [competitors, loadData]);

  const handleAddSubmit = async (e) => {
    e.preventDefault();
    setFormError(null);
    setIsSubmitting(true);
    
    const validUrls = newUrls.filter(u => u.trim() !== '');
    if (validUrls.length === 0) {
      setFormError("Please enter at least one URL.");
      setIsSubmitting(false);
      return;
    }
    
    try {
      await auditsApi.addCompetitors(id, validUrls);
      setShowForm(false);
      setNewUrls(['', '', '']);
      loadData();
    } catch (err) {
      setFormError(err.message || "Failed to add competitors.");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading && !baseAudit) {
    return <div style={{ padding: 'var(--space-8)', textAlign: 'center' }}>Loading...</div>;
  }

  if (error) {
    return (
      <div className="comp-page">
        <Card>
          <EmptyState icon={<AlertCircle size={24} color="var(--sev-critical)" />} title="Error" description={error} />
        </Card>
      </div>
    );
  }

  return (
    <div className="comp-page">
      <div className="comp-page__header">
        <div>
          <h2 className="comp-page__title">Competitor Analysis</h2>
          <p className="comp-page__subtitle">{baseAudit?.url}</p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
          <Button as={Link} to={`/audit/${id}`} variant="secondary" size="sm">
            Back to Audit
          </Button>
          {!showForm && competitors.length < 3 && (
            <Button onClick={() => setShowForm(true)} variant="primary" size="sm" icon={<PlusCircle size={14} />}>
              Add Competitors
            </Button>
          )}
        </div>
      </div>

      {showForm && (
        <Card className="comp-form">
          <h3 style={{ marginBottom: 'var(--space-4)' }}>Compare with competitors</h3>
          <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)', marginBottom: 'var(--space-4)' }}>
            Enter up to {3 - competitors.length} competitor URLs.
          </p>
          <form onSubmit={handleAddSubmit}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
              {Array.from({ length: 3 - competitors.length }).map((_, i) => (
                <input
                  key={i}
                  type="url"
                  placeholder="https://competitor.com"
                  className="comp-input"
                  value={newUrls[i]}
                  onChange={e => {
                    const next = [...newUrls];
                    next[i] = e.target.value;
                    setNewUrls(next);
                  }}
                />
              ))}
            </div>
            {formError && (
              <div className="error-alert" style={{ marginBottom: 'var(--space-4)' }}>
                {formError}
              </div>
            )}
            <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
              <Button type="submit" variant="primary" loading={isSubmitting}>Analyze Competitors</Button>
              <Button type="button" variant="secondary" onClick={() => setShowForm(false)}>Cancel</Button>
            </div>
          </form>
        </Card>
      )}

      {competitors.length > 0 && (
        <div className="comp-status-list">
          {competitors.map(c => {
            const audit = c.competitor_audit;
            const isWorking = ['pending', 'crawling', 'analyzing'].includes(audit.status);
            return (
              <div key={c.id} className="comp-status-item">
                <div style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  <strong>{audit.url}</strong>
                </div>
                <div>
                  {isWorking && <Badge variant="info"><RefreshCw size={12} className="spin" style={{marginRight: 4}}/> {audit.status}</Badge>}
                  {audit.status === 'completed' && <Badge variant="success"><CheckCircle size={12} style={{marginRight: 4}}/> Completed</Badge>}
                  {audit.status === 'failed' && <Badge variant="critical"><AlertCircle size={12} style={{marginRight: 4}}/> Failed</Badge>}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {competitors.length === 0 && !showForm && (
        <Card>
          <EmptyState
            icon={<BarChart2 size={32} />}
            title="No Competitors Yet"
            description="Add competitor URLs to see how your website compares."
            actions={
              <Button onClick={() => setShowForm(true)} variant="primary" icon={<PlusCircle size={14} />}>
                Add Competitors
              </Button>
            }
          />
        </Card>
      )}

      {isComparing && (
        <div style={{ textAlign: 'center', padding: 'var(--space-8)' }}>
          <RefreshCw className="spin" size={24} style={{ marginBottom: 'var(--space-3)' }} />
          <p>Generating comparison...</p>
        </div>
      )}

      {comparison && (
        <div className="comp-dashboard">
          
          <h3 className="comp-section-title">Overall Score</h3>
          <div className="comp-scores">
            <CompScoreCard 
              title="My Website" 
              score={comparison.base_seo_score} 
              grade={comparison.base_seo_grade} 
            />
            {comparison.competitors.map(c => (
              <CompScoreCard 
                key={c.competitor_audit_id}
                title={c.competitor_url}
                score={c.seo_score}
                grade={c.seo_grade}
              />
            ))}
          </div>

          <h3 className="comp-section-title">Metric Comparison</h3>
          <Card padding="none">
            <div className="comp-table-wrap">
              <table className="comp-table">
                <thead>
                  <tr>
                    <th>Metric</th>
                    {comparison.competitors.map(c => (
                      <th key={c.competitor_audit_id}>{c.competitor_url}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {comparison.competitors[0]?.metrics.map(m => (
                    <tr key={m.metric}>
                      <td style={{ fontWeight: '500' }}>{m.metric}</td>
                      {comparison.competitors.map(c => {
                        const cm = c.metrics.find(x => x.metric === m.metric);
                        return (
                          <td key={c.competitor_audit_id}>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                              <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-secondary)' }}>
                                Me: {cm.user_value}
                              </span>
                              <span style={{ fontSize: 'var(--font-size-sm)', fontWeight: '500' }}>
                                Comp: {cm.competitor_value}
                              </span>
                              <Badge 
                                variant={cm.difference === 'Equal' ? 'neutral' : (cm.difference.includes('You') ? 'success' : 'critical')}
                              >
                                {cm.difference}
                              </Badge>
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <h3 className="comp-section-title">SEO Gaps</h3>
          {comparison.competitors.map(c => (
            <div key={c.competitor_audit_id} style={{ marginBottom: 'var(--space-6)' }}>
              <h4 style={{ marginBottom: 'var(--space-3)', fontSize: 'var(--font-size-lg)' }}>vs {c.competitor_url}</h4>
              {c.gaps.length === 0 ? (
                <Card>
                  <p>No actionable SEO gaps found against this competitor!</p>
                </Card>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                  {c.gaps.map((gap, i) => (
                    <Card key={i} className="gap-card">
                      <div className="gap-card__header">
                        <Badge severity={gap.severity} />
                        <span style={{ fontWeight: '600' }}>{gap.metric}</span>
                        <Badge variant="neutral">{gap.category}</Badge>
                      </div>
                      <p className="gap-card__desc">{gap.explanation}</p>
                      <div className="gap-card__stats">
                        <div><span className="gap-card__label">You:</span> {gap.user_value}</div>
                        <div><span className="gap-card__label">Competitor:</span> {gap.competitor_value}</div>
                      </div>
                      <div className="gap-card__rec">
                        <strong>Recommendation:</strong> {gap.recommended_action}
                      </div>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          ))}

        </div>
      )}
    </div>
  );
}
