import './Card.css';

/**
 * Card
 *
 * Props:
 *   padding    - 'none' | 'sm' | 'md'  (default: 'md')
 *   interactive - bool — adds hover state
 *   className  - additional classes
 *   as         - element tag (default: 'div')
 */
export default function Card({
  padding = 'md',
  interactive = false,
  className = '',
  as: Tag = 'div',
  children,
  ...props
}) {
  const classes = [
    'card',
    padding === 'md' ? 'card--padded' : '',
    padding === 'sm' ? 'card--sm' : '',
    interactive ? 'card--interactive' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <Tag className={classes} {...props}>
      {children}
    </Tag>
  );
}
