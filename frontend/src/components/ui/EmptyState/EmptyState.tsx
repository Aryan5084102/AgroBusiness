import type { ReactNode } from 'react';
import { Icon, type IconName } from '@/components/ui/Icon/Icon';
import styles from './EmptyState.module.scss';

interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: IconName;
  action?: ReactNode;
  tone?: 'neutral' | 'danger';
}

/** Shown when a list has no rows, or a filter matched nothing. Always says what
 * to do next rather than leaving a blank panel. */
export function EmptyState({
  title,
  description,
  icon = 'info',
  action,
  tone = 'neutral',
}: EmptyStateProps) {
  return (
    <div className={`${styles.wrap} ${tone === 'danger' ? styles.danger : ''}`}>
      <span className={styles.icon}>
        <Icon name={icon} size={22} />
      </span>
      <p className={styles.title}>{title}</p>
      {description ? <p className={styles.description}>{description}</p> : null}
      {action ? <div className={styles.action}>{action}</div> : null}
    </div>
  );
}
