import { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { RefreshCw, Search, CheckCircle, AlertTriangle, AlertCircle, TrendingUp, Lightbulb } from 'lucide-react';
import { auditsApi } from '../api/audits';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import EmptyState from '../components/ui/EmptyState';
import './KeywordsPage.css';

export default function KeywordsPage() {
  const { id } = useParams();
  
  const [baseAudit, setBaseAudit] = useState(null);
  const [keywordsData, setKeywordsData] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const [inputKeywords, setInputKeywords] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [formError, setFormError] = useState(null);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [auditRes, kwRes] = await Promise.all([
        auditsApi.getAudit(id),
        fetch(`/api/audits/${id}/keywords`).then(r => r.json())
      ]);
      setBaseAudit(auditRes);
      if (Array.isArray(kwRes)) {
        setKeywordsData(kwRes);
      }
    } catch (err) {
      setError(err.message || 'Failed to load keywords data.');
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleAnalyze = async (e) => {
    e.preventDefault();
    setFormError(null);
    const kws = inputKeywords.split(',').map(k => k.trim()).filter(k => k);
    if (kws.length === 0) {
      setFormError("Please enter at least one keyword.");
      return;
    }
    
    setIsAnalyzing(true);
    try {
      const res = await fetch(`/api/audits/${id}/keywords/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keywords: kws })
      });
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Failed to analyze keywords.");
      }
      const data = await res.json();
      
      // Merge with existing
      const nextKws = [...keywordsData];
      data.forEach(newKw => {
        const idx = nextKws.findIndex(k => k.keyword === newKw.keyword);
        if (idx >= 0) nextKws[idx] = newKw;
        else nextKws.unshift(newKw); // add to top
      });
      setKeywordsData(nextKws);
      setInputKeywords('');
    } catch (err) {
      setFormError(err.message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  if (isLoading && !baseAudit) {
    return <div style={{ padding: 'var(--space-8)', textAlign: 'center' }}>Loading...</div>;
  }

  if (error) {
    return (
      <div className="kw-page">
        <Card>
          <EmptyState icon={<AlertCircle size={24} color="var(--sev-critical)" />} title="Error" description={error} />
        </Card>
      </div>
    );
  }

  return (
    <div className="kw-page">
      <div className="kw-page__header">
        <div>
          <h2 className="kw-page__title">Keyword Research & Opportunities</h2>
          <p className="kw-page__subtitle">{baseAudit?.url}</p>
        </div>
        <Button as={Link} to={`/audit/${id}`} variant="secondary" size="sm">
          Back to Audit
        </Button>
      </div>

      <Card className="kw-form">
        <h3 style={{ marginBottom: 'var(--space-2)' }}>Analyze Keywords</h3>
        <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)', marginBottom: 'var(--space-4)' }}>
          Enter a target keyword or comma-separated list of keywords to analyze against your website content.
        </p>
        <form onSubmit={handleAnalyze} style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'flex-start' }}>
          <div style={{ flex: 1 }}>
            <input
              type="text"
              placeholder="e.g. technical seo, seo audit checklist"
              className="kw-input"
              value={inputKeywords}
              onChange={e => setInputKeywords(e.target.value)}
            />
            {formError && (
              <div className="error-alert" style={{ marginTop: 'var(--space-2)' }}>
                {formError}
              </div>
            )}
          </div>
          <Button type="submit" variant="primary" loading={isAnalyzing} icon={<Search size={14} />}>
            Analyze
          </Button>
        </form>
      </Card>

      {keywordsData.length === 0 ? (
        <Card>
          <EmptyState
            icon={<TrendingUp size={32} />}
            title="No Keywords Analyzed"
            description="Enter keywords above to discover content opportunities."
          />
        </Card>
      ) : (
        <div className="kw-list">
          {keywordsData.map(kw => (
            <Card key={kw.id} className="kw-card">
              <div className="kw-card__header">
                <div>
                  <h3 className="kw-card__title">{kw.keyword}</h3>
                  <Badge variant="neutral">{kw.intent}</Badge>
                </div>
                <div className="kw-card__score-box">
                  <span className="kw-card__score-label">Opportunity Score</span>
                  <span className={`kw-card__score-val ${kw.opportunity_score >= 80 ? 'text-success' : kw.opportunity_score >= 50 ? 'text-warning' : 'text-danger'}`}>
                    {kw.opportunity_score}/100
                  </span>
                </div>
              </div>

              <div className="kw-card__stats">
                <div className="kw-stat">
                  <span className="kw-stat__label">Page Coverage</span>
                  <span className="kw-stat__val">{kw.usage.pages_containing} / {kw.usage.total_pages_crawled}</span>
                </div>
                <div className="kw-stat">
                  <span className="kw-stat__label">Title Tags</span>
                  <span className="kw-stat__val">{kw.usage.title_matches}</span>
                </div>
                <div className="kw-stat">
                  <span className="kw-stat__label">H1 Tags</span>
                  <span className="kw-stat__val">{kw.usage.h1_matches}</span>
                </div>
                <div className="kw-stat">
                  <span className="kw-stat__label">Meta Descriptions</span>
                  <span className="kw-stat__val">{kw.usage.meta_matches}</span>
                </div>
              </div>

              <div className="kw-card__sections">
                <div className="kw-section">
                  <h4 className="kw-section__title"><AlertTriangle size={14} /> Content Gaps</h4>
                  {kw.gaps.length === 0 ? (
                    <p className="text-sm text-success" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <CheckCircle size={14} /> No major gaps found!
                    </p>
                  ) : (
                    <ul className="kw-gap-list">
                      {kw.gaps.map((gap, i) => (
                        <li key={i}>
                          <strong>{gap.type}:</strong> {gap.description}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <div className="kw-section">
                  <h4 className="kw-section__title"><Lightbulb size={14} /> Related Suggestions</h4>
                  {kw.suggestions.length === 0 ? (
                    <p className="text-sm text-muted">No suggestions available.</p>
                  ) : (
                    <div className="kw-suggestions">
                      {kw.suggestions.map((sug, i) => (
                        <Badge key={i} variant="outline">{sug}</Badge>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
