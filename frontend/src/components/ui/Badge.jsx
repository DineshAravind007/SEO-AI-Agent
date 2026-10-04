import './Badge.css';

const SEVERITY_VARIANT = {
  CRITICAL: 'critical',
  HIGH:     'high',
  MEDIUM:   'medium',
  LOW:      'low',
};

/**
 * Badge
 *
 * Props:
 *   variant - 'critical' | 'high' | 'medium' | 'low' | 'neutral' | 'success' | 'info'
 *   severity - shorthand: pass raw severity string ('CRITICAL' etc.) to auto-map variant
 */
export default function Badge({ variant, severity, className = '', children, ...props }) {
  const resolvedVariant =
    variant ?? (severity ? (SEVERITY_VARIANT[severity.toUpperCase()] ?? 'neutral') : 'neutral');

  return (
    <span
      className={`badge badge--${resolvedVariant} ${className}`.trim()}
      {...props}
    >
      {children ?? (severity ?? '')}
    </span>
  );
}
