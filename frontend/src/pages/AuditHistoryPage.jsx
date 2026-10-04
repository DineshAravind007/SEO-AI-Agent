import { Link } from 'react-router-dom';
import { Clock, PlusCircle } from 'lucide-react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import EmptyState from '../components/ui/EmptyState';
import './PlaceholderPage.css';

export default function AuditHistoryPage() {
  return (
    <div className="placeholder-page">
      <div className="placeholder-page__header">
        <h2 className="placeholder-page__title">Audit History</h2>
        <p className="placeholder-page__subtitle">
          All SEO audits you have run, with their scores and status.
        </p>
      </div>

      <Card>
        <EmptyState
          icon={<Clock size={22} strokeWidth={1.5} />}
          title="No audits yet"
          description="Once you run your first audit, all past audits will appear here with their URL, status, score, and issue counts."
          actions={
            <Button as={Link} to="/audit/new" variant="primary" icon={<PlusCircle size={14} strokeWidth={2} />}>
              Start New Audit
            </Button>
          }
        />
      </Card>
    </div>
  );
}
