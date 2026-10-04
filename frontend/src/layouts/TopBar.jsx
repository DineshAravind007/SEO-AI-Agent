import { Link } from 'react-router-dom';
import { Menu, PlusCircle, Search } from 'lucide-react';
import Button from '../components/ui/Button';
import './TopBar.css';

export default function TopBar({ pageTitle, onMenuClick }) {
  return (
    <header className="topbar" role="banner">
      {/* Hamburger — mobile only */}
      <button
        type="button"
        className="topbar__menu-btn"
        onClick={onMenuClick}
        aria-label="Open navigation menu"
      >
        <Menu size={20} strokeWidth={1.75} />
      </button>

      {/* Brand — mobile only */}
      <Link to="/dashboard" className="topbar__mobile-brand" aria-label="SEO Agent home">
        <span className="topbar__mobile-brand-mark" aria-hidden="true">
          <Search size={13} color="#fff" strokeWidth={2.5} />
        </span>
        <span className="topbar__mobile-brand-name">SEO Agent</span>
      </Link>

      {/* Page title — desktop */}
      {pageTitle && (
        <h1 className="topbar__page-title">{pageTitle}</h1>
      )}

      <div className="topbar__spacer" aria-hidden="true" />

      {/* Actions */}
      <div className="topbar__actions">
        <Button as={Link} to="/audit/new" size="sm" variant="primary" icon={<PlusCircle size={14} strokeWidth={2} />}>
          New Audit
        </Button>
      </div>
    </header>
  );
}
