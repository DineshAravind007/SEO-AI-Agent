import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Mail, Lock, Eye, EyeOff, User, Search, AlertCircle, UserPlus } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import './AuthPage.css';

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState({ name: '', email: '', password: '', confirm: '' });
  const [errors, setErrors] = useState({});
  const [globalError, setGlobalError] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);

  function validate() {
    const e = {};
    if (!form.name.trim()) e.name = 'Full name is required.';
    if (!form.email.trim()) e.email = 'Email is required.';
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) e.email = 'Enter a valid email address.';
    if (!form.password) e.password = 'Password is required.';
    else if (form.password.length < 8) e.password = 'Password must be at least 8 characters.';
    if (!form.confirm) e.confirm = 'Please confirm your password.';
    else if (form.confirm !== form.password) e.confirm = 'Passwords do not match.';
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
      await register(form.email.trim(), form.password, form.name.trim());
      navigate('/dashboard', { replace: true });
    } catch (err) {
      setGlobalError(err.message || 'Registration failed. Please try again.');
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
      {/* ── Left: Branding panel ─────────────────────── */}
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
            Start your<br />
            <span>SEO journey</span><br />
            today — free
          </h2>
          <p className="auth-page__brand-description">
            Join thousands of teams using SEO Agent to audit their sites,
            track keyword opportunities, and grow their organic presence with AI.
          </p>
        </div>

        <div className="auth-page__features">
          {[
            { icon: '✅', label: 'No credit card required' },
            { icon: '🚀', label: 'Run your first audit in 60 seconds' },
            { icon: '🔒', label: 'Your data stays private and secure' },
            { icon: '📊', label: 'Unlimited audits on your plan' },
          ].map(({ icon, label }) => (
            <div key={label} className="auth-page__feature">
              <span className="auth-page__feature-icon">{icon}</span>
              <span>{label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Right: Form panel ────────────────────────── */}
      <div className="auth-page__form-panel">
        <div className="auth-page__form-container">
          <div className="auth-page__form-header">
            <h1 className="auth-page__form-title">Create your account</h1>
            <p className="auth-page__form-subtitle">
              Already have an account?{' '}
              <Link to="/login">Sign in</Link>
            </p>
          </div>

          <form className="auth-form" onSubmit={handleSubmit} noValidate id="register-form">
            {globalError && (
              <div className="auth-form__error-banner" role="alert">
                <AlertCircle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
                {globalError}
              </div>
            )}

            {/* Name */}
            <div className="auth-form__group">
              <label htmlFor="reg-name" className="auth-form__label">Full name</label>
              <div className="auth-form__input-wrapper">
                <span className="auth-form__input-icon">
                  <User size={15} />
                </span>
                <input
                  id="reg-name"
                  type="text"
                  autoComplete="name"
                  placeholder="Jane Smith"
                  value={form.name}
                  onChange={handleChange('name')}
                  className={`auth-form__input${errors.name ? ' auth-form__input--error' : ''}`}
                  aria-describedby={errors.name ? 'reg-name-error' : undefined}
                />
              </div>
              {errors.name && (
                <span id="reg-name-error" className="auth-form__field-error" role="alert">{errors.name}</span>
              )}
            </div>

            {/* Email */}
            <div className="auth-form__group">
              <label htmlFor="reg-email" className="auth-form__label">Email address</label>
              <div className="auth-form__input-wrapper">
                <span className="auth-form__input-icon">
                  <Mail size={15} />
                </span>
                <input
                  id="reg-email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@company.com"
                  value={form.email}
                  onChange={handleChange('email')}
                  className={`auth-form__input${errors.email ? ' auth-form__input--error' : ''}`}
                  aria-describedby={errors.email ? 'reg-email-error' : undefined}
                />
              </div>
              {errors.email && (
                <span id="reg-email-error" className="auth-form__field-error" role="alert">{errors.email}</span>
              )}
            </div>

            {/* Password */}
            <div className="auth-form__group">
              <label htmlFor="reg-password" className="auth-form__label">Password</label>
              <div className="auth-form__input-wrapper">
                <span className="auth-form__input-icon">
                  <Lock size={15} />
                </span>
                <input
                  id="reg-password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  placeholder="Min. 8 characters"
                  value={form.password}
                  onChange={handleChange('password')}
                  className={`auth-form__input${errors.password ? ' auth-form__input--error' : ''}`}
                  aria-describedby={errors.password ? 'reg-password-error' : undefined}
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
                <span id="reg-password-error" className="auth-form__field-error" role="alert">{errors.password}</span>
              )}
            </div>

            {/* Confirm Password */}
            <div className="auth-form__group">
              <label htmlFor="reg-confirm" className="auth-form__label">Confirm password</label>
              <div className="auth-form__input-wrapper">
                <span className="auth-form__input-icon">
                  <Lock size={15} />
                </span>
                <input
                  id="reg-confirm"
                  type={showConfirm ? 'text' : 'password'}
                  autoComplete="new-password"
                  placeholder="Re-enter password"
                  value={form.confirm}
                  onChange={handleChange('confirm')}
                  className={`auth-form__input${errors.confirm ? ' auth-form__input--error' : ''}`}
                  aria-describedby={errors.confirm ? 'reg-confirm-error' : undefined}
                />
                <button
                  type="button"
                  className="auth-form__toggle-btn"
                  onClick={() => setShowConfirm((v) => !v)}
                  aria-label={showConfirm ? 'Hide password' : 'Show password'}
                >
                  {showConfirm ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
              {errors.confirm && (
                <span id="reg-confirm-error" className="auth-form__field-error" role="alert">{errors.confirm}</span>
              )}
            </div>

            <button
              id="register-submit-btn"
              type="submit"
              className="auth-form__submit"
              disabled={loading}
            >
              {loading ? (
                <>
                  <span className="auth-spinner" aria-hidden="true" />
                  Creating account…
                </>
              ) : (
                <>
                  <UserPlus size={15} />
                  Create account
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
