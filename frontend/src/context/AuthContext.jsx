import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { authApi } from '../api/auth';
import { tokenStorage } from '../api/client';

const AuthContext = createContext(null);

/**
 * Global authentication state provider.
 *
 * Exposes:
 *   user        – null | { id, email, name, is_active }
 *   loading     – true while the initial /me check is in-flight
 *   login(email, password) – authenticates and stores token
 *   register(email, password, name) – creates account then auto-logs-in
 *   logout()    – clears token and user state
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true); // true on mount while we check /me

  // On mount: if a token exists, restore session from /api/auth/me
  useEffect(() => {
    const token = tokenStorage.get();
    if (!token) {
      setLoading(false);
      return;
    }
    authApi
      .me()
      .then((data) => setUser(data))
      .catch(() => {
        // Token is stale/invalid — clear it
        tokenStorage.remove();
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email, password) => {
    const data = await authApi.login({ email, password });
    tokenStorage.set(data.access_token);
    // Fetch full user profile after login
    const me = await authApi.me();
    setUser(me);
    return me;
  }, []);

  const register = useCallback(async (email, password, name) => {
    await authApi.register({ email, password, name });
    // Auto-login after successful registration
    return login(email, password);
  }, [login]);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // Best-effort; always clear local state
    }
    tokenStorage.remove();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>');
  return ctx;
}
