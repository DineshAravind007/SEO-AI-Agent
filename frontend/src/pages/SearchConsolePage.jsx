import { useState, useEffect } from 'react';
import { 
  BarChart2, Plug, AlertCircle, TrendingUp, CheckCircle, Search, FileText
} from 'lucide-react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import EmptyState from '../components/ui/EmptyState';
import './SearchConsolePage.css';

export default function SearchConsolePage() {
  const [status, setStatus] = useState(null);
  const [sites, setSites] = useState([]);
  const [selectedSite, setSelectedSite] = useState('');
  
  // Date range state
  const [dateRange, setDateRange] = useState('28');
  
  const [performance, setPerformance] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isPerfLoading, setIsPerfLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadStatus();
  }, []);

  const loadStatus = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/gsc/status');
      if (!res.ok) throw new Error("Failed to fetch GSC status");
      const data = await res.json();
      setStatus(data);
      
      if (data.configured && data.connected) {
        await loadSites();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const loadSites = async () => {
    try {
      const res = await fetch('/api/gsc/sites');
      if (!res.ok) throw new Error("Failed to fetch sites");
      const data = await res.json();
      setSites(data);
      if (data.length > 0) {
        setSelectedSite(data[0].siteUrl);
      }
    } catch (err) {
      setError("Error loading GSC sites: " + err.message);
    }
  };

  useEffect(() => {
    if (selectedSite) {
      fetchPerformance();
    }
  }, [selectedSite, dateRange]);

  const fetchPerformance = async () => {
    setIsPerfLoading(true);
    setError(null);
    try {
      // Calculate dates
      const end = new Date();
      const start = new Date();
      start.setDate(end.getDate() - parseInt(dateRange));
      
      const req = {
        site_url: selectedSite,
        start_date: start.toISOString().split('T')[0],
        end_date: end.toISOString().split('T')[0]
      };
      
      const res = await fetch('/api/gsc/performance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req)
      });
      
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Failed to fetch performance data.");
      }
      
      const data = await res.json();
      setPerformance(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsPerfLoading(false);
    }
  };

  const handleConnect = () => {
    window.location.href = '/api/gsc/auth/login';
  };

  if (isLoading) {
    return <div style={{ padding: 'var(--space-8)', textAlign: 'center' }}>Loading...</div>;
  }

  // 1. Not configured state
  if (status && !status.configured) {
    return (
      <div className="gsc-page">
        <h2 className="gsc-page__title">Google Search Console</h2>
        <Card>
          <EmptyState 
            icon={<Plug size={32} />}
            title="Google Search Console is not configured"
            description="To use this feature, the backend must be configured with Google OAuth credentials (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET). Please check the environment configuration."
          />
        </Card>
      </div>
    );
  }

  // 2. Not connected state
  if (status && status.configured && !status.connected) {
    return (
      <div className="gsc-page">
        <h2 className="gsc-page__title">Google Search Console</h2>
        <Card>
          <EmptyState 
            icon={<BarChart2 size={32} color="var(--color-primary)" />}
            title="Connect Google Search Console"
            description="Authenticate with Google to view real search performance data, top queries, and CTR."
          />
          <div style={{ display: 'flex', justifyContent: 'center', marginTop: 'var(--space-4)' }}>
            <Button onClick={handleConnect} variant="primary">
              Connect with Google
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  // 3 & 4. Connected State
  return (
    <div className="gsc-page">
      <div className="gsc-page__header">
        <h2 className="gsc-page__title">Google Search Console</h2>
      </div>

      {error && (
        <Card className="error-card" style={{ marginBottom: 'var(--space-4)' }}>
          <AlertCircle size={20} color="var(--sev-critical)" /> {error}
        </Card>
      )}

      <Card className="gsc-controls">
        <div className="gsc-controls__group">
          <label>Property</label>
          <select 
            className="gsc-select" 
            value={selectedSite} 
            onChange={e => setSelectedSite(e.target.value)}
          >
            <option value="">Select a property...</option>
            {sites.map(s => (
              <option key={s.siteUrl} value={s.siteUrl}>{s.siteUrl}</option>
            ))}
          </select>
        </div>
        <div className="gsc-controls__group">
          <label>Date Range</label>
          <select 
            className="gsc-select" 
            value={dateRange} 
            onChange={e => setDateRange(e.target.value)}
          >
            <option value="7">Last 7 Days</option>
            <option value="28">Last 28 Days</option>
            <option value="90">Last 3 Months</option>
          </select>
        </div>
      </Card>

      {!selectedSite ? (
        <Card>
          <EmptyState title="Select a property" description="Choose a Google Search Console property from the dropdown above to view performance." />
        </Card>
      ) : isPerfLoading ? (
        <Card><div style={{ textAlign: 'center', padding: 'var(--space-6)' }}>Fetching Search Console data...</div></Card>
      ) : performance ? (
        <div className="gsc-dashboard">
          <div className="gsc-metrics-grid">
            <Card className="gsc-metric-card">
              <span className="gsc-metric__label">Total Clicks</span>
              <span className="gsc-metric__val text-primary">{performance.summary.clicks.toLocaleString()}</span>
            </Card>
            <Card className="gsc-metric-card">
              <span className="gsc-metric__label">Total Impressions</span>
              <span className="gsc-metric__val text-primary">{performance.summary.impressions.toLocaleString()}</span>
            </Card>
            <Card className="gsc-metric-card">
              <span className="gsc-metric__label">Average CTR</span>
              <span className="gsc-metric__val">{(performance.summary.ctr * 100).toFixed(2)}%</span>
            </Card>
            <Card className="gsc-metric-card">
              <span className="gsc-metric__label">Average Position</span>
              <span className="gsc-metric__val">{performance.summary.position.toFixed(1)}</span>
            </Card>
          </div>

          <div className="gsc-tables-grid">
            <Card className="gsc-table-card">
              <h3 className="gsc-table__title"><Search size={16} /> Top Search Queries</h3>
              <div className="table-responsive">
                <table className="gsc-table">
                  <thead>
                    <tr>
                      <th>Query</th>
                      <th>Clicks</th>
                      <th>Impressions</th>
                      <th>CTR</th>
                      <th>Pos</th>
                    </tr>
                  </thead>
                  <tbody>
                    {performance.queries.length === 0 && (
                      <tr><td colSpan="5" style={{ textAlign: 'center' }}>No queries found.</td></tr>
                    )}
                    {performance.queries.map((q, i) => (
                      <tr key={i}>
                        <td className="truncate-text" title={q.query}>{q.query}</td>
                        <td>{q.clicks}</td>
                        <td>{q.impressions}</td>
                        <td>{(q.ctr * 100).toFixed(1)}%</td>
                        <td>{q.position.toFixed(1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

            <Card className="gsc-table-card">
              <h3 className="gsc-table__title"><FileText size={16} /> Top Pages</h3>
              <div className="table-responsive">
                <table className="gsc-table">
                  <thead>
                    <tr>
                      <th>Page</th>
                      <th>Clicks</th>
                      <th>Impressions</th>
                      <th>CTR</th>
                      <th>Pos</th>
                    </tr>
                  </thead>
                  <tbody>
                    {performance.pages.length === 0 && (
                      <tr><td colSpan="5" style={{ textAlign: 'center' }}>No pages found.</td></tr>
                    )}
                    {performance.pages.map((p, i) => (
                      <tr key={i}>
                        <td className="truncate-text" title={p.page}>
                          {p.page.replace(selectedSite, '/')}
                        </td>
                        <td>{p.clicks}</td>
                        <td>{p.impressions}</td>
                        <td>{(p.ctr * 100).toFixed(1)}%</td>
                        <td>{p.position.toFixed(1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>
        </div>
      ) : null}
    </div>
  );
}
