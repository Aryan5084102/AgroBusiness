import type { ReactNode } from 'react';
import styles from './Badge.module.scss';

export type BadgeTone = 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'brand';

interface BadgeProps {
  children: ReactNode;
  tone?: BadgeTone;
  /** Adds a leading dot — useful for statuses in dense tables. */
  dot?: boolean;
}

/** Compact status pill. Tone carries the meaning; never colour alone — the
 * label always states the status in words too. */
export function Badge({ children, tone = 'neutral', dot = false }: BadgeProps) {
  return (
    <span className={`${styles.badge} ${styles[tone]}`}>
      {dot ? <span className={styles.dot} aria-hidden="true" /> : null}
      {children}
    </span>
  );
}

// Shared status → tone mapping so the same words look the same everywhere.
const STATUS_TONES: Record<string, BadgeTone> = {
  paid: 'success',
  partial: 'warning',
  credit: 'danger',
  confirmed: 'info',
  quotation: 'neutral',
  dispatched: 'info',
  invoiced: 'success',
  partially_dispatched: 'warning',
  cancelled: 'danger',
  received: 'info',
  under_inspection: 'info',
  estimate_prepared: 'neutral',
  awaiting_approval: 'warning',
  approved: 'info',
  in_progress: 'warning',
  waiting_for_part: 'warning',
  quality_check: 'info',
  ready: 'success',
  delivered: 'success',
  active: 'success',
  inactive: 'neutral',
  retail: 'neutral',
  wholesale: 'brand',
};

export function statusTone(status: string): BadgeTone {
  return STATUS_TONES[status] ?? 'neutral';
}

/** Turns `partially_dispatched` into `Partially dispatched`. */
export function humanize(value: string): string {
  const spaced = value.replace(/_/g, ' ');
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <Badge tone={statusTone(status)} dot>
      {humanize(status)}
    </Badge>
  );
}
