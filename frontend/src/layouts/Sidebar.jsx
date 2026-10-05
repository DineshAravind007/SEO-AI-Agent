import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  PlusCircle,
  Clock,
  AlertTriangle,
  Sparkles,
  Search,
  Activity,
} from 'lucide-react';
import './Sidebar.css';

const NAV_SECTIONS = [
  {
    id: 'main',
    items: [
      { path: '/dashboard', label: 'Dashboard',  Icon: LayoutDashboard },
      { path: '/audit/new', label: 'New Audit',  Icon: PlusCircle },
    ],
  },
  {
    id: 'analysis',
    label: 'Analysis',
    items: [
      { path: '/audits',           label: 'Audit History',      Icon: Clock },
      { path: '/monitoring',       label: 'Monitoring',         Icon: Activity },
      { path: '/issues',           label: 'Issues',             Icon: AlertTriangle },
      { path: '/recommendations',  label: 'AI Recommendations', Icon: Sparkles },
      { path: '/gsc',              label: 'Search Console',     Icon: LayoutDashboard },
    ],
  },
  {
    id: 'settings',
    label: 'Settings',
    items: [
      { path: '/settings/notifications', label: 'Notifications', Icon: AlertTriangle },
    ],
  },
];

export default function Sidebar({ isOpen, onClose }) {
  return (
    <nav
      className={`sidebar${isOpen ? ' sidebar--open' : ''}`}
      aria-label="Primary navigation"
    >
      {/* Brand */}
      <NavLink to="/dashboard" className="sidebar__brand" onClick={onClose} aria-label="SEO Agent home">
        <span className="sidebar__logo-mark" aria-hidden="true">
          <Search size={16} color="#fff" strokeWidth={2.5} />
        </span>
        <span className="sidebar__brand-text">
          <span className="sidebar__brand-name">SEO Agent</span>
          <span className="sidebar__brand-sub">AI-Powered Analysis</span>
        </span>
      </NavLink>

      {/* Navigation */}
      <div className="sidebar__nav">
        {NAV_SECTIONS.map((section, si) => (
          <div key={section.id}>
            {si > 0 && <div className="sidebar__divider" role="separator" />}
            {section.label && (
              <p className="sidebar__section-label">{section.label}</p>
            )}
            {section.items.map(({ path, label, Icon }) => (
              <NavLink
                key={path}
                to={path}
                className={({ isActive }) =>
                  `sidebar__link${isActive ? ' sidebar__link--active' : ''}`
                }
                onClick={onClose}
                aria-current={undefined}
              >
                <span className="sidebar__link-icon" aria-hidden="true">
                  <Icon size={16} strokeWidth={1.75} />
                </span>
                <span className="sidebar__link-label">{label}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="sidebar__footer">
        <div className="sidebar__footer-status">
          <span className="sidebar__status-dot" aria-hidden="true" />
          <span>SEO Agent v1.0</span>
        </div>
      </div>
    </nav>
  );
}
