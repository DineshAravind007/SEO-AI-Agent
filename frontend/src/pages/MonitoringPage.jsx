import { useState, useEffect, useCallback } from 'react';
import {
  Activity, Plus, Play, Pause, RefreshCw, Eye, Trash2,
  TrendingUp, TrendingDown, Minus, Globe, BarChart2, Clock,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Badge from '../components/ui/Badge';
import EmptyState from '../components/ui/EmptyState';
import { monitoringApi } from '../api/monitoring';
import './MonitoringPage.css';

function ScoreChange({ change }) {
  if (change === null || change === undefined) return <span className="score-change--none">—</span>;
  if (change > 0) return (
    <span className="score-change score-change--up">
      <TrendingUp size={12} /> +{change}
    </span>
  );
  if (change < 0) return (
    <span className="score-change score-change--down">
      <TrendingDown size={12} /> {change}
    </span>
  );
  return <span className="score-change score-change--none"><Minus size={12} /> 0</span>;
}

function ScoreBadge({ score }) {
  if (score === null || score === undefined) return <span className="text-muted">—</span>;
  let cls = 'score-badge';
  if (score >= 80) cls += ' score-badge--good';
  else if (score >= 60) cls += ' score-badge--fair';
  else cls += ' score-badge--poor';
  return <span className={cls}>{score}</span>;
}

function formatDate(dateStr) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

export default function MonitoringPage() {
  const [projects, setProjects] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [runningIds, setRunningIds] = useState(new Set());

  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ url: '', name: '', frequency: 'weekly', max_pages: 10, max_depth: 2 });
  const [formError, setFormError] = useState(null);
  const [isCreating, setIsCreating] = useState(false);

  const navigate = useNavigate();

  const fetchProjects = useCallback(async () => {
    try {
      const data = await monitoringApi.listProjects();
      setProjects(data);
      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to load projects');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchProjects(); }, [fetchProjects]);

  const handleCreate = async (e) => {
    e.preventDefault();
    setFormError(null);
    setIsCreating(true);
    try {
      await monitoringApi.createProject({
        url: form.url,
        name: form.name,
        frequency: form.frequency,
        max_pages: Number(form.max_pages),
        max_depth: Number(form.max_depth),
      });
      setShowModal(false);
      setForm({ url: '', name: '', frequency: 'weekly', max_pages: 10, max_depth: 2 });
      fetchProjects();
    } catch (err) {
      setFormError(err.message || 'Failed to create project');
    } finally {
      setIsCreating(false);
    }
  };

  const handleToggleStatus = async (id, currentStatus) => {
    try {
      await monitoringApi.updateProject(id, { is_active: !currentStatus });
      fetchProjects();
    } catch (err) {
      alert(err.message || 'Failed to update status');
    }
  };

  const handleRunNow = async (id) => {
    if (runningIds.has(id)) return;
    setRunningIds(prev => new Set([...prev, id]));
    try {
      await monitoringApi.runNow(id);
      // Give user feedback then poll
      setTimeout(fetchProjects, 1500);
    } catch (err) {
      alert(err.message || 'Failed to trigger audit');
    } finally {
      // Remove running state after a moment
      setTimeout(() => setRunningIds(prev => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      }), 3000);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this monitoring project? This cannot be undone.')) return;
    try {
      await monitoringApi.deleteProject(id);
      fetchProjects();
    } catch (err) {
      alert(err.message || 'Failed to delete project');
    }
  };

  // Summary metrics
  const activeCount = projects.filter(p => p.is_active).length;
  const scores = projects.filter(p => p.last_score !== null && p.last_score !== undefined).map(p => p.last_score);
  const avgScore = scores.length > 0 ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : null;
  const lastAuditDates = projects
    .filter(p => p.last_audit_date)
    .map(p => new Date(p.last_audit_date))
    .sort((a, b) => b - a);
  const lastAuditStr = lastAuditDates.length > 0 ? formatDate(lastAuditDates[0].toISOString()) : '—';

  if (isLoading) {
    return (
      <div className="mon-page">
        <div className="mon-loading">
          <Activity size={32} className="mon-loading__icon" />
          <span>Loading monitoring projects…</span>
        </div>
      </div>
    );
  }

  return (
    <div className="mon-page">
      <div className="mon-page__header">
        <div>
          <h1 className="mon-page__title">SEO Monitoring</h1>
          <p className="mon-page__subtitle">Track your website's SEO performance over time</p>
        </div>
        <Button id="btn-new-project" onClick={() => setShowModal(true)} variant="primary">
          <Plus size={16} /> New Project
        </Button>
      </div>

      {error && <div className="error-alert" role="alert">{error}</div>}

      {/* Summary cards */}
      <div className="mon-overview">
        <Card className="mon-overview__card">
          <div className="mon-overview__icon-wrap mon-overview__icon-wrap--blue">
            <Globe size={20} />
          </div>
          <div className="mon-overview__content">
            <span className="mon-overview__label">Monitored Websites</span>
            <span className="mon-overview__val">{projects.length}</span>
          </div>
        </Card>
        <Card className="mon-overview__card">
          <div className="mon-overview__icon-wrap mon-overview__icon-wrap--green">
            <Activity size={20} />
          </div>
          <div className="mon-overview__content">
            <span className="mon-overview__label">Active Monitoring</span>
            <span className="mon-overview__val">{activeCount}</span>
          </div>
        </Card>
        <Card className="mon-overview__card">
          <div className="mon-overview__icon-wrap mon-overview__icon-wrap--purple">
            <BarChart2 size={20} />
          </div>
          <div className="mon-overview__content">
            <span className="mon-overview__label">Average SEO Score</span>
            <span className="mon-overview__val">{avgScore !== null ? avgScore : '—'}</span>
          </div>
        </Card>
        <Card className="mon-overview__card">
          <div className="mon-overview__icon-wrap mon-overview__icon-wrap--orange">
            <Clock size={20} />
          </div>
          <div className="mon-overview__content">
            <span className="mon-overview__label">Last Audit</span>
            <span className="mon-overview__val mon-overview__val--sm">{lastAuditStr}</span>
          </div>
        </Card>
      </div>

      {/* Projects table */}
      <Card className="mon-list-card">
        {projects.length === 0 ? (
          <EmptyState
            icon={<Activity size={32} />}
            title="No monitoring projects yet"
            description="Create your first monitoring project to automatically track your website's SEO performance over time."
            actions={
              <Button id="btn-empty-new-project" onClick={() => setShowModal(true)} variant="primary">
                <Plus size={16} /> Create Project
              </Button>
            }
          />
        ) : (
          <div className="table-responsive">
            <table className="mon-table" aria-label="Monitoring projects">
              <thead>
                <tr>
                  <th>Website</th>
                  <th>Status</th>
                  <th>Frequency</th>
                  <th>Last Audit</th>
                  <th>Score</th>
                  <th>Change</th>
                  <th>Next Audit</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {projects.map(p => (
                  <tr key={p.id} className="mon-table__row">
                    <td className="mon-col-name">
                      <div className="mon-col-name__primary">{p.name}</div>
                      <div className="mon-col-name__url" title={p.url}>{p.url}</div>
                    </td>
                    <td>
                      <Badge variant={p.is_active ? 'success' : 'neutral'}>
                        {p.is_active ? 'Active' : 'Paused'}
                      </Badge>
                    </td>
                    <td className="mon-col-freq">{p.frequency.charAt(0).toUpperCase() + p.frequency.slice(1)}</td>
                    <td className="mon-col-date">{formatDate(p.last_audit_date)}</td>
                    <td><ScoreBadge score={p.last_score} /></td>
                    <td><ScoreChange change={p.score_change} /></td>
                    <td className="mon-col-date">{formatDate(p.next_audit_date)}</td>
                    <td className="mon-actions">
                      <Button
                        id={`btn-view-${p.id}`}
                        onClick={() => navigate(`/monitoring/${p.id}`)}
                        variant="outline"
                        size="sm"
                        title="View Detail"
                      >
                        <Eye size={13} />
                      </Button>
                      <Button
                        id={`btn-run-${p.id}`}
                        onClick={() => handleRunNow(p.id)}
                        variant="outline"
                        size="sm"
                        title="Run Audit Now"
                        disabled={!p.is_active || runningIds.has(p.id)}
                      >
                        <RefreshCw size={13} className={runningIds.has(p.id) ? 'spin' : ''} />
                      </Button>
                      <Button
                        id={`btn-toggle-${p.id}`}
                        onClick={() => handleToggleStatus(p.id, p.is_active)}
                        variant="outline"
                        size="sm"
                        title={p.is_active ? 'Pause' : 'Resume'}
                      >
                        {p.is_active ? <Pause size={13} /> : <Play size={13} />}
                      </Button>
                      <Button
                        id={`btn-delete-${p.id}`}
                        onClick={() => handleDelete(p.id)}
                        variant="outline"
                        size="sm"
                        className="btn-danger"
                        title="Delete"
                      >
                        <Trash2 size={13} />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Create project modal */}
      {showModal && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="modal-title">
          <Card className="modal-content">
            <h2 id="modal-title" className="modal-title">New Monitoring Project</h2>

            {formError && <div className="error-alert" style={{ marginBottom: 'var(--space-4)' }}>{formError}</div>}

            <form onSubmit={handleCreate}>
              <div className="form-group">
                <label htmlFor="mon-url">Website URL</label>
                <input
                  id="mon-url"
                  required
                  type="url"
                  value={form.url}
                  onChange={e => setForm(f => ({ ...f, url: e.target.value }))}
                  placeholder="https://example.com"
                />
              </div>
              <div className="form-group">
                <label htmlFor="mon-name">Project Name</label>
                <input
                  id="mon-name"
                  required
                  type="text"
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="My Blog"
                />
              </div>
              <div className="form-group">
                <label htmlFor="mon-freq">Monitoring Frequency</label>
                <select
                  id="mon-freq"
                  value={form.frequency}
                  onChange={e => setForm(f => ({ ...f, frequency: e.target.value }))}
                >
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                </select>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="mon-max-pages">Max Pages (1–50)</label>
                  <input
                    id="mon-max-pages"
                    type="number"
                    min={1}
                    max={50}
                    value={form.max_pages}
                    onChange={e => setForm(f => ({ ...f, max_pages: e.target.value }))}
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="mon-max-depth">Max Depth (1–5)</label>
                  <input
                    id="mon-max-depth"
                    type="number"
                    min={1}
                    max={5}
                    value={form.max_depth}
                    onChange={e => setForm(f => ({ ...f, max_depth: e.target.value }))}
                  />
                </div>
              </div>
              <div className="modal-actions">
                <Button
                  id="btn-modal-cancel"
                  type="button"
                  variant="outline"
                  onClick={() => { setShowModal(false); setFormError(null); }}
                >
                  Cancel
                </Button>
                <Button id="btn-modal-create" type="submit" variant="primary" disabled={isCreating}>
                  {isCreating ? 'Creating…' : 'Create Project'}
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </div>
  );
}
