import type { ReactNode } from 'react';
import { Icon, type IconName } from '@/components/ui/Icon/Icon';
import { Skeleton } from '@/components/ui/Skeleton';
import styles from './StatCard.module.scss';

export type StatTone = 'default' | 'positive' | 'warning' | 'danger';

interface StatCardProps {
  label: string;
  value: ReactNode;
  hint?: string;
  icon?: IconName;
  tone?: StatTone;
  isLoading?: boolean;
}

/** One headline number with its label. Grouped by <StatGrid> on dashboards. */
export function StatCard({
  label,
  value,
  hint,
  icon,
  tone = 'default',
  isLoading = false,
}: StatCardProps) {
  return (
    <article className={`${styles.card} ${styles[tone]}`}>
      <div className={styles.top}>
        <span className={styles.label}>{label}</span>
        {icon ? (
          <span className={styles.icon}>
            <Icon name={icon} size={16} />
          </span>
        ) : null}
      </div>
      {isLoading ? (
        <Skeleton height={26} width="70%" />
      ) : (
        <p className={`${styles.value} tabular-nums`}>{value}</p>
      )}
      {hint ? <p className={styles.hint}>{hint}</p> : null}
    </article>
  );
}

export function StatGrid({ children }: { children: ReactNode }) {
  return <div className={styles.grid}>{children}</div>;
}
