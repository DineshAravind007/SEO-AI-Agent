import { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Mail, Lock, Eye, EyeOff, Search, AlertCircle, LogIn } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import './AuthPage.css';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = location.state?.from?.pathname || '/dashboard';

  const [form, setForm] = useState({ email: '', password: '' });
  const [errors, setErrors] = useState({});
  const [globalError, setGlobalError] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  function validate() {
    const e = {};
    if (!form.email.trim()) e.email = 'Email is required.';
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) e.email = 'Enter a valid email address.';
    if (!form.password) e.password = 'Password is required.';
    return e;
  }

  async function handleSubmit(evt) {
    evt.preventDefault();
    setGlobalError('');
    const e = validate();
    setErrors(e);
    if (Object.keys(e).length > 0) return;

    setLoading(true);
    try {
      await login(form.email.trim(), form.password);
      navigate(from, { replace: true });
    } catch (err) {
      setGlobalError(err.message || 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  }

  function handleChange(field) {
    return (e) => {
      setForm((prev) => ({ ...prev, [field]: e.target.value }));
      if (errors[field]) setErrors((prev) => ({ ...prev, [field]: '' }));
      setGlobalError('');
    };
  }

  return (
    <div className="auth-page">
      {/* ── Left: Branding panel ───────────────────────── */}
      <div className="auth-page__brand" aria-hidden="true">
        <div className="auth-page__brand-logo">
          <span className="auth-page__brand-mark">
            <Search size={18} color="#fff" strokeWidth={2.5} />
          </span>
          <span>
            <div className="auth-page__brand-name">SEO Agent</div>
            <div className="auth-page__brand-tagline">AI-Powered Analysis</div>
          </span>
        </div>

        <div className="auth-page__brand-hero">
          <h2 className="auth-page__brand-headline">
            Supercharge your<br />
            <span>SEO strategy</span><br />
            with AI insights
          </h2>
          <p className="auth-page__brand-description">
            Crawl your website, identify technical issues, track rankings,
            and receive AI-powered recommendations — all in one platform.
          </p>
        </div>

        <div className="auth-page__features">
          {[
            { icon: '🔍', label: 'Full-site crawl & technical audit' },
            { icon: '🤖', label: 'AI-powered SEO recommendations' },
            { icon: '📈', label: 'Automated monitoring & alerts' },
            { icon: '🔑', label: 'Google Search Console integration' },
          ].map(({ icon, label }) => (
            <div key={label} className="auth-page__feature">
              <span className="auth-page__feature-icon">{icon}</span>
              <span>{label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Right: Form panel ─────────────────────────── */}
      <div className="auth-page__form-panel">
        <div className="auth-page__form-container">
          <div className="auth-page__form-header">
            <h1 className="auth-page__form-title">Welcome back</h1>
            <p className="auth-page__form-subtitle">
              Don't have an account?{' '}
              <Link to="/register">Create one free</Link>
            </p>
          </div>

          <form className="auth-form" onSubmit={handleSubmit} noValidate id="login-form">
            {globalError && (
              <div className="auth-form__error-banner" role="alert">
                <AlertCircle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
                {globalError}
              </div>
            )}

            {/* Email */}
            <div className="auth-form__group">
              <label htmlFor="login-email" className="auth-form__label">Email address</label>
              <div className="auth-form__input-wrapper">
                <span className="auth-form__input-icon">
                  <Mail size={15} />
                </span>
                <input
                  id="login-email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@company.com"
                  value={form.email}
                  onChange={handleChange('email')}
                  className={`auth-form__input${errors.email ? ' auth-form__input--error' : ''}`}
                  aria-describedby={errors.email ? 'login-email-error' : undefined}
                />
              </div>
              {errors.email && (
                <span id="login-email-error" className="auth-form__field-error" role="alert">{errors.email}</span>
              )}
            </div>

            {/* Password */}
            <div className="auth-form__group">
              <label htmlFor="login-password" className="auth-form__label">Password</label>
              <div className="auth-form__input-wrapper">
                <span className="auth-form__input-icon">
                  <Lock size={15} />
                </span>
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="••••••••"
                  value={form.password}
                  onChange={handleChange('password')}
                  className={`auth-form__input${errors.password ? ' auth-form__input--error' : ''}`}
                  aria-describedby={errors.password ? 'login-password-error' : undefined}
                />
                <button
                  type="button"
                  className="auth-form__toggle-btn"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
              {errors.password && (
                <span id="login-password-error" className="auth-form__field-error" role="alert">{errors.password}</span>
              )}
            </div>

            <button
              id="login-submit-btn"
              type="submit"
              className="auth-form__submit"
              disabled={loading}
            >
              {loading ? (
                <>
                  <span className="auth-spinner" aria-hidden="true" />
                  Signing in…
                </>
              ) : (
                <>
                  <LogIn size={15} />
                  Sign in
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
