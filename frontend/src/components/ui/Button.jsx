import './Button.css';

/**
 * Button / ButtonLink
 *
 * Props:
 *   variant  - 'primary' | 'secondary' | 'ghost' | 'danger'   (default: 'secondary')
 *   size     - 'sm' | 'md' | 'lg'                             (default: 'md')
 *   as       - element type, e.g. 'a' or Link component        (default: 'button')
 *   loading  - bool
 *   disabled - bool
 *   icon     - ReactNode (left icon)
 *   iconRight - ReactNode (right icon)
 *   className - additional classes
 */
export default function Button({
  variant = 'secondary',
  size = 'md',
  as: Tag = 'button',
  loading = false,
  disabled = false,
  icon,
  iconRight,
  className = '',
  children,
  ...props
}) {
  const classes = [
    'btn',
    `btn--${variant}`,
    `btn--${size}`,
    loading ? 'btn--loading' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  const isButton = Tag === 'button';

  return (
    <Tag
      className={classes}
      disabled={isButton ? disabled || loading : undefined}
      aria-disabled={!isButton && (disabled || loading) ? true : undefined}
      {...props}
    >
      {loading ? (
        <span className="btn__spinner" aria-hidden="true" />
      ) : (
        icon && <span aria-hidden="true">{icon}</span>
      )}
      {children}
      {!loading && iconRight && <span aria-hidden="true">{iconRight}</span>}
    </Tag>
  );
}
