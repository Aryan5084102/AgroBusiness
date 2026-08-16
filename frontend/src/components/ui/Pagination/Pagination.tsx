'use client';

import { Icon } from '@/components/ui/Icon/Icon';
import styles from './Pagination.module.scss';

interface PaginationProps {
  total: number;
  limit: number;
  offset: number;
  onOffsetChange: (offset: number) => void;
  /** What the rows are, for the "1–25 of 120 products" summary. */
  noun?: string;
}

/** Offset pager matching the backend's limit/offset list contract. */
export function Pagination({
  total,
  limit,
  offset,
  onOffsetChange,
  noun = 'rows',
}: PaginationProps) {
  if (total === 0) return null;
  const first = offset + 1;
  const last = Math.min(offset + limit, total);
  const hasPrevious = offset > 0;
  const hasNext = last < total;

  return (
    <nav className={styles.pagination} aria-label="Pagination">
      <p className={styles.summary}>
        <span className="tabular-nums">
          {first}–{last}
        </span>{' '}
        of <span className="tabular-nums">{total}</span> {noun}
      </p>
      <div className={styles.controls}>
        <button
          type="button"
          className={styles.button}
          disabled={!hasPrevious}
          onClick={() => onOffsetChange(Math.max(0, offset - limit))}
        >
          <Icon name="chevronLeft" size={16} />
          Previous
        </button>
        <button
          type="button"
          className={styles.button}
          disabled={!hasNext}
          onClick={() => onOffsetChange(offset + limit)}
        >
          Next
          <Icon name="chevronRight" size={16} />
        </button>
      </div>
    </nav>
  );
}
