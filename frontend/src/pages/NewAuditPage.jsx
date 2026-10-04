import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Play } from 'lucide-react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { auditsApi } from '../api/audits';
import '../components/ui/Form.css';
import './PlaceholderPage.css';

export default function NewAuditPage() {
  const navigate = useNavigate();
  
  const [url, setUrl] = useState('');
  const [maxPages, setMaxPages] = useState(10);
  const [maxDepth, setMaxDepth] = useState(2);
  
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [validationErrors, setValidationErrors] = useState({});

  const validate = () => {
    const errs = {};
    if (!url) {
      errs.url = 'Website URL is required.';
    } else {
      try {
        new URL(url);
      } catch (_) {
        errs.url = 'Please enter a valid URL (e.g., https://example.com).';
      }
    }

    if (maxPages < 1 || maxPages > 50) {
      errs.maxPages = 'Maximum pages must be between 1 and 50.';
    }

    if (maxDepth < 0 || maxDepth > 3) {
      errs.maxDepth = 'Maximum depth must be between 0 and 3.';
    }

    setValidationErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    
    if (!validate()) return;
    
    setIsSubmitting(true);
    
    try {
      const response = await auditsApi.createAudit(url, maxPages, maxDepth);
      navigate(`/audit/${response.id}`);
    } catch (err) {
      setError(err.message || 'Failed to start audit. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="placeholder-page">
      <div className="placeholder-page__header">
        <h2 className="placeholder-page__title">New Audit</h2>
        <p className="placeholder-page__subtitle">
          Enter a website URL to start a comprehensive SEO analysis.
        </p>
      </div>

      <Card style={{ maxWidth: '600px' }}>
        <form onSubmit={handleSubmit}>
          {error && <div className="error-alert" role="alert">{error}</div>}

          <div className="form-group">
            <label htmlFor="url" className="form-label">Website URL</label>
            <input
              id="url"
              type="url"
              className="form-input"
              placeholder="https://example.com"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={isSubmitting}
              autoFocus
            />
            {validationErrors.url && <div className="form-error-text">{validationErrors.url}</div>}
            <div className="form-help-text">Must include http:// or https://</div>
          </div>

          <div className="form-group">
            <label htmlFor="maxPages" className="form-label">Maximum Pages to Crawl</label>
            <input
              id="maxPages"
              type="number"
              min="1"
              max="50"
              className="form-input"
              value={maxPages}
              onChange={(e) => setMaxPages(parseInt(e.target.value, 10))}
              disabled={isSubmitting}
            />
            {validationErrors.maxPages && <div className="form-error-text">{validationErrors.maxPages}</div>}
            <div className="form-help-text">Limits the crawler (1-50 pages).</div>
          </div>

          <div className="form-group">
            <label htmlFor="maxDepth" className="form-label">Crawl Depth</label>
            <input
              id="maxDepth"
              type="number"
              min="0"
              max="3"
              className="form-input"
              value={maxDepth}
              onChange={(e) => setMaxDepth(parseInt(e.target.value, 10))}
              disabled={isSubmitting}
            />
            {validationErrors.maxDepth && <div className="form-error-text">{validationErrors.maxDepth}</div>}
            <div className="form-help-text">How many clicks away from the start URL (0-3).</div>
          </div>

          <div style={{ marginTop: 'var(--space-6)' }}>
            <Button 
              type="submit" 
              variant="primary" 
              loading={isSubmitting}
              icon={<Play size={16} />}
            >
              Start Analysis
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
