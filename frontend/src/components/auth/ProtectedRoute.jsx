import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

/**
 * Wraps any route that requires authentication.
 * - While the auth state is loading, renders nothing (avoids flash of login page).
 * - If unauthenticated, redirects to /login with the original `from` location stored,
 *   so we can redirect back after a successful login.
 * - If authenticated, renders children.
 */
export default function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    // Still restoring session — render nothing to avoid flicker
    return null;
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}
