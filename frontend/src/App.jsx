import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/auth/ProtectedRoute';
import AppLayout from './layouts/AppLayout';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import NewAuditPage from './pages/NewAuditPage';
import AuditResultPage from './pages/AuditResultPage';
import AuditHistoryPage from './pages/AuditHistoryPage';
import IssuesPage from './pages/IssuesPage';
import RecommendationsPage from './pages/RecommendationsPage';
import CompetitorsPage from './pages/CompetitorsPage';
import KeywordsPage from './pages/KeywordsPage';
import SearchConsolePage from './pages/SearchConsolePage';
import MonitoringPage from './pages/MonitoringPage';
import MonitoringDetailPage from './pages/MonitoringDetailPage';

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        {/* ── Public auth routes ─────────────────────── */}
        <Route path="/login"    element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        {/* Redirect root to dashboard (protected) */}
        <Route path="/" element={<Navigate to="/dashboard" replace />} />

        {/* ── Protected application shell ────────────── */}
        <Route
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/dashboard"       element={<DashboardPage />} />
          <Route path="/audit/new"       element={<NewAuditPage />} />
          <Route path="/audit/:id"       element={<AuditResultPage />} />
          <Route path="/audit/:id/recommendations" element={<RecommendationsPage />} />
          <Route path="/audit/:id/competitors"     element={<CompetitorsPage />} />
          <Route path="/audit/:id/keywords"        element={<KeywordsPage />} />
          <Route path="/gsc"             element={<SearchConsolePage />} />
          <Route path="/monitoring"      element={<MonitoringPage />} />
          <Route path="/monitoring/:id"  element={<MonitoringDetailPage />} />
          <Route path="/audits"          element={<AuditHistoryPage />} />
          <Route path="/issues"          element={<IssuesPage />} />
          <Route path="/recommendations" element={<RecommendationsPage />} />
        </Route>

        {/* 404 fallback */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </AuthProvider>
  );
}
