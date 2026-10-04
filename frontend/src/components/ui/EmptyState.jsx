import './EmptyState.css';

/**
 * EmptyState
 *
 * Props:
 *   icon        - ReactNode
 *   title       - string
 *   description - string
 *   actions     - ReactNode
 */
export default function EmptyState({ icon, title, description, actions }) {
  return (
    <div className="empty-state" role="status" aria-live="polite">
      {icon && (
        <div className="empty-state__icon" aria-hidden="true">
          {icon}
        </div>
      )}
      {title && <p className="empty-state__title">{title}</p>}
      {description && <p className="empty-state__description">{description}</p>}
      {actions && <div className="empty-state__actions">{actions}</div>}
    </div>
  );
}
