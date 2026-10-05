import { useState, useRef, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Menu, PlusCircle, Search, LogOut, User, ChevronDown } from 'lucide-react';
import Button from '../components/ui/Button';
import { useAuth } from '../context/AuthContext';
import './TopBar.css';

export default function TopBar({ pageTitle, onMenuClick }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  // Close dropdown on outside click
  useEffect(() => {
    function onClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    }
    if (menuOpen) document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, [menuOpen]);

  async function handleLogout() {
    setMenuOpen(false);
    await logout();
    navigate('/login', { replace: true });
  }

  // Generate initials for avatar
  const initials = user?.name
    ? user.name.split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase()
    : user?.email?.[0]?.toUpperCase() ?? '?';

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

        {user && (
          <div className="topbar__user-menu" ref={menuRef}>
            <button
              type="button"
              id="topbar-user-menu-btn"
              className="topbar__user-btn"
              onClick={() => setMenuOpen((v) => !v)}
              aria-haspopup="true"
              aria-expanded={menuOpen}
              aria-label="User menu"
            >
              <span className="topbar__avatar" aria-hidden="true">{initials}</span>
              <span className="topbar__user-name">{user.name || user.email}</span>
              <ChevronDown size={14} className={`topbar__chevron${menuOpen ? ' topbar__chevron--open' : ''}`} />
            </button>

            {menuOpen && (
              <div className="topbar__dropdown" role="menu" aria-label="User options">
                <div className="topbar__dropdown-header">
                  <p className="topbar__dropdown-name">{user.name || 'User'}</p>
                  <p className="topbar__dropdown-email">{user.email}</p>
                </div>
                <div className="topbar__dropdown-divider" />
                <button
                  type="button"
                  id="topbar-logout-btn"
                  className="topbar__dropdown-item topbar__dropdown-item--danger"
                  role="menuitem"
                  onClick={handleLogout}
                >
                  <LogOut size={14} />
                  Sign out
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
