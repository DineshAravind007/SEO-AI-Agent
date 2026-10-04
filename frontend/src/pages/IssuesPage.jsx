import { Link } from 'react-router-dom';
import { AlertTriangle, PlusCircle } from 'lucide-react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import EmptyState from '../components/ui/EmptyState';
import './PlaceholderPage.css';

export default function IssuesPage() {
  return (
    <div className="placeholder-page">
      <div className="placeholder-page__header">
        <h2 className="placeholder-page__title">Issues</h2>
        <p className="placeholder-page__subtitle">
          Detected on-page and technical SEO issues, grouped by severity.
        </p>
      </div>

      <Card>
        <EmptyState
          icon={<AlertTriangle size={22} strokeWidth={1.5} />}
          title="No issues to display"
          description="SEO issues from completed audits will appear here, grouped by severity — Critical, High, Medium, and Low."
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
