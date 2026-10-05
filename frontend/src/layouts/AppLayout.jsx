import { useState, useEffect, useCallback } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import TopBar from './TopBar';
import './AppLayout.css';

const PAGE_TITLES = {
  '/dashboard':       'Dashboard',
  '/audit/new':       'New Audit',
  '/audits':          'Audit History',
  '/issues':          'Issues',
  '/recommendations': 'AI Recommendations',
  '/gsc':             'Google Search Console',
  '/monitoring':      'Automated Monitoring',
};

export default function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  const closeSidebar = useCallback(() => setSidebarOpen(false), []);

  // Close sidebar on route change (mobile UX)
  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  // Close sidebar on Escape key
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') closeSidebar(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [closeSidebar]);

  // Prevent body scroll when mobile sidebar is open
  useEffect(() => {
    document.body.style.overflow = sidebarOpen ? 'hidden' : '';
    return () => { document.body.style.overflow = ''; };
  }, [sidebarOpen]);

  const pageTitle = PAGE_TITLES[location.pathname] ?? '';

  return (
    <div className="app-layout">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="app-layout__overlay"
          role="presentation"
          aria-hidden="true"
          onClick={closeSidebar}
        />
      )}

      <Sidebar isOpen={sidebarOpen} onClose={closeSidebar} />

      <div className="app-layout__body">
        <TopBar
          pageTitle={pageTitle}
          onMenuClick={() => setSidebarOpen((v) => !v)}
        />
        <main className="app-layout__content" id="main-content" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
