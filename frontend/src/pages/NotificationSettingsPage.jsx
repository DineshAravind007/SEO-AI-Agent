import React, { useState, useEffect, useCallback } from 'react';
import { Bell, CheckCircle, AlertCircle, Save } from 'lucide-react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { notificationsApi } from '../api/notifications';

export default function NotificationSettingsPage() {
  const [preferences, setPreferences] = useState(null);
  const [history, setHistory] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  const fetchSettings = useCallback(async () => {
    try {
      const [prefsData, historyData] = await Promise.all([
        notificationsApi.getPreferences(),
        notificationsApi.getHistory()
      ]);
      setPreferences(prefsData);
      setHistory(historyData);
    } catch (err) {
      setError(err.message || 'Failed to load notification settings');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const handleToggle = (key) => {
    setPreferences(prev => ({ ...prev, [key]: !prev[key] }));
    setSuccess(false);
  };

  const handleSave = async () => {
    setIsSaving(true);
    setError(null);
    setSuccess(false);
    try {
      await notificationsApi.updatePreferences(preferences);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err.message || 'Failed to save settings');
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return <div className="p-8 text-center text-muted">Loading settings...</div>;
  }

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Bell className="text-primary" />
            Notification Settings
          </h1>
          <p className="text-muted mt-1">Manage how and when you receive SEO alerts.</p>
        </div>
      </div>

      {error && (
        <div className="bg-danger/10 text-danger p-4 rounded-md flex items-start gap-3">
          <AlertCircle className="shrink-0 mt-0.5" size={18} />
          <div>{error}</div>
        </div>
      )}

      {success && (
        <div className="bg-success/10 text-success p-4 rounded-md flex items-center gap-3">
          <CheckCircle size={18} />
          <span>Settings saved successfully.</span>
        </div>
      )}

      <Card>
        <div className="p-6 space-y-6">
          <h3 className="text-lg font-semibold border-b border-border pb-2">Email Alerts</h3>
          
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-surface-hover rounded-md">
              <div>
                <div className="font-medium">Enable Email Notifications</div>
                <div className="text-sm text-muted">Receive alerts at your registered email address</div>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input 
                  type="checkbox" 
                  className="sr-only peer"
                  checked={preferences?.email_enabled || false}
                  onChange={() => handleToggle('email_enabled')}
                />
                <div className="w-11 h-6 bg-border peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
              </label>
            </div>

            <div className={`space-y-4 transition-opacity ${!preferences?.email_enabled ? 'opacity-50 pointer-events-none' : ''}`}>
              <div className="flex items-center justify-between p-4 border border-border rounded-md">
                <div>
                  <div className="font-medium">SEO Score Drop</div>
                  <div className="text-sm text-muted">Notify me when my score drops by 5 points or more</div>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input 
                    type="checkbox" 
                    className="sr-only peer"
                    checked={preferences?.score_drop_alert || false}
                    onChange={() => handleToggle('score_drop_alert')}
                  />
                  <div className="w-11 h-6 bg-border rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
                </label>
              </div>

              <div className="flex items-center justify-between p-4 border border-border rounded-md">
                <div>
                  <div className="font-medium">Critical Issues</div>
                  <div className="text-sm text-muted">Notify me immediately when new critical SEO issues are detected</div>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input 
                    type="checkbox" 
                    className="sr-only peer"
                    checked={preferences?.critical_issue_alert || false}
                    onChange={() => handleToggle('critical_issue_alert')}
                  />
                  <div className="w-11 h-6 bg-border rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
                </label>
              </div>

              <div className="flex items-center justify-between p-4 border border-border rounded-md">
                <div>
                  <div className="font-medium">High Issues</div>
                  <div className="text-sm text-muted">Notify me when new high-severity issues are detected</div>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input 
                    type="checkbox" 
                    className="sr-only peer"
                    checked={preferences?.high_issue_alert || false}
                    onChange={() => handleToggle('high_issue_alert')}
                  />
                  <div className="w-11 h-6 bg-border rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
                </label>
              </div>
              
              <div className="flex items-center justify-between p-4 border border-border rounded-md">
                <div>
                  <div className="font-medium">Weekly Summary</div>
                  <div className="text-sm text-muted">Send a weekly digest of my monitoring projects</div>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input 
                    type="checkbox" 
                    className="sr-only peer"
                    checked={preferences?.weekly_summary || false}
                    onChange={() => handleToggle('weekly_summary')}
                  />
                  <div className="w-11 h-6 bg-border rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
                </label>
              </div>
            </div>
          </div>
          
          <div className="pt-4 flex justify-end">
            <Button onClick={handleSave} disabled={isSaving} className="flex items-center gap-2">
              <Save size={16} />
              {isSaving ? 'Saving...' : 'Save Settings'}
            </Button>
          </div>
        </div>
      </Card>

      <Card>
        <div className="p-6">
          <h3 className="text-lg font-semibold mb-4">Notification History</h3>
          {history.length === 0 ? (
            <div className="text-center py-8 text-muted bg-surface-hover rounded-md">
              No notifications have been sent yet.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-xs uppercase bg-surface-hover text-muted">
                  <tr>
                    <th className="px-4 py-3 rounded-tl-md">Date</th>
                    <th className="px-4 py-3">Type</th>
                    <th className="px-4 py-3">Severity</th>
                    <th className="px-4 py-3">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {history.slice(0, 10).map((item) => (
                    <tr key={item.id} className="border-b border-border last:border-0">
                      <td className="px-4 py-3 whitespace-nowrap">
                        {new Date(item.sent_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-3 font-medium capitalize">
                        {item.notification_type.replace('_', ' ')}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-1 rounded text-xs font-semibold ${
                          item.severity === 'CRITICAL' ? 'bg-danger/20 text-danger' :
                          item.severity === 'HIGH' ? 'bg-warning/20 text-warning' :
                          'bg-surface-hover text-muted-foreground'
                        }`}>
                          {item.severity}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`flex items-center gap-1 ${
                          item.status === 'sent' ? 'text-success' :
                          item.status === 'failed' ? 'text-danger' : 'text-muted'
                        }`}>
                          {item.status === 'sent' && <CheckCircle size={14} />}
                          {item.status === 'failed' && <AlertCircle size={14} title={item.error_message} />}
                          <span className="capitalize">{item.status}</span>
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
