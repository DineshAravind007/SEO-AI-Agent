import { Routes, Route, Navigate } from 'react-router-dom';
import AppLayout from './layouts/AppLayout';
import DashboardPage from './pages/DashboardPage';
import NewAuditPage from './pages/NewAuditPage';
import AuditResultPage from './pages/AuditResultPage';
import AuditHistoryPage from './pages/AuditHistoryPage';
import IssuesPage from './pages/IssuesPage';
import RecommendationsPage from './pages/RecommendationsPage';
import CompetitorsPage from './pages/CompetitorsPage';
import KeywordsPage from './pages/KeywordsPage';
import SearchConsolePage from './pages/SearchConsolePage';

export default function App() {
  return (
    <Routes>
      {/* Redirect root to dashboard */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />

      {/* Main application shell */}
      <Route element={<AppLayout />}>
        <Route path="/dashboard"       element={<DashboardPage />} />
        <Route path="/audit/new"       element={<NewAuditPage />} />
        <Route path="/audit/:id"       element={<AuditResultPage />} />
        <Route path="/audit/:id/recommendations" element={<RecommendationsPage />} />
        <Route path="/audit/:id/competitors" element={<CompetitorsPage />} />        
        <Route path="/audit/:id/keywords" element={<KeywordsPage />} />        
        <Route path="/gsc" element={<SearchConsolePage />} />        
        {/* Placeholders for global views */}
        <Route path="/audits"          element={<AuditHistoryPage />} />
        <Route path="/issues"          element={<IssuesPage />} />
        <Route path="/recommendations" element={<RecommendationsPage />} />
      </Route>

      {/* 404 fallback */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
