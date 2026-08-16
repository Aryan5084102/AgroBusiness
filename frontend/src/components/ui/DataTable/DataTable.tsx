'use client';

import type { ReactNode } from 'react';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';
import styles from './DataTable.module.scss';

export interface Column<T> {
  /** Stable key; also used as the React key for cells. */
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  /** Right-align and use tabular figures — for money and quantities. */
  numeric?: boolean;
  /** Hidden below the tablet breakpoint so phones show only what matters. */
  secondary?: boolean;
  width?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  isLoading?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: ReactNode;
  onRowClick?: (row: T) => void;
  /** Rendered under the body — totals, notes. */
  footer?: ReactNode;
  caption?: string;
}

/**
 * The single table used across the app: sticky header, zebra-free hairlines,
 * numeric alignment, its own horizontal scroll container, plus built-in
 * loading and empty states so no screen has to reinvent them.
 */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  isLoading = false,
  emptyTitle = 'Nothing here yet',
  emptyDescription,
  emptyAction,
  onRowClick,
  footer,
  caption,
}: DataTableProps<T>) {
  if (isLoading) {
    return (
      <div className={styles.loading}>
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} height={44} />
        ))}
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <EmptyState
        title={emptyTitle}
        description={emptyDescription}
        action={emptyAction}
      />
    );
  }

  return (
    <div className={styles.scroll}>
      <table className={styles.table}>
        {caption ? <caption className={styles.caption}>{caption}</caption> : null}
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                style={column.width ? { width: column.width } : undefined}
                className={[
                  column.numeric ? styles.numeric : '',
                  column.secondary ? styles.secondary : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              className={onRowClick ? styles.clickable : undefined}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              tabIndex={onRowClick ? 0 : undefined}
              onKeyDown={
                onRowClick
                  ? (event) => {
                      if (event.key === 'Enter') onRowClick(row);
                    }
                  : undefined
              }
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={[
                    column.numeric ? `${styles.numeric} tabular-nums` : '',
                    column.secondary ? styles.secondary : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                >
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
        {footer ? <tfoot>{footer}</tfoot> : null}
      </table>
    </div>
  );
}
