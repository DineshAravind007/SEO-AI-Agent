import { apiClient } from './client';

export const authApi = {
  /**
   * Register a new user account.
   * @param {{ email: string, password: string, name?: string }} data
   */
  register: (data) => apiClient.post('/api/auth/register', data),

  /**
   * Login and receive a JWT access token.
   * @param {{ email: string, password: string }} data
   */
  login: (data) => apiClient.post('/api/auth/login', data),

  /**
   * Logout — clears the server-side session (if any) and notifies the caller.
   */
  logout: () => apiClient.post('/api/auth/logout', {}),

  /**
   * Fetch the authenticated user's profile.
   */
  me: () => apiClient.get('/api/auth/me'),
};
