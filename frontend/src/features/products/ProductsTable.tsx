'use client';

import { useState } from 'react';
import { formatCurrency, formatPercent } from '@/lib/formatting/currency';
import { useProducts } from './useProducts';
import styles from './ProductsTable.module.scss';

const PAGE_SIZE = 25;

// Server-paginated, debounced-search product list with loading/empty/error states.
export function ProductsTable() {
  const [search, setSearch] = useState('');
  const [offset, setOffset] = useState(0);
  const { data, isLoading, isError, isFetching } = useProducts({
    search: search || undefined,
    limit: PAGE_SIZE,
    offset,
  });

  const onSearch = (value: string) => {
    setSearch(value);
    setOffset(0);
  };

  const total = data?.total ?? 0;
  const items = data?.items ?? [];
  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div>
      <div className={styles.toolbar}>
        <input
          type="search"
          className={styles.search}
          placeholder="Search by name, SKU or barcode…"
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          aria-label="Search products"
        />
        {isFetching ? <span className={styles.fetching}>Updating…</span> : null}
      </div>

      {isError ? (
        <p role="alert" className={styles.error}>
          Could not load products. Please try again.
        </p>
      ) : null}

      {isLoading ? (
        <div className={styles.skeleton} aria-hidden="true">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className={styles.skeletonRow} />
          ))}
        </div>
      ) : items.length === 0 ? (
        <p className={styles.empty}>No products found.</p>
      ) : (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Name</th>
                <th>SKU</th>
                <th className={styles.num}>Retail</th>
                <th className={styles.num}>Wholesale</th>
                <th className={styles.num}>GST</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((p) => (
                <tr key={p.id}>
                  <td>{p.name}</td>
                  <td className={styles.mono}>{p.sku}</td>
                  <td className={`${styles.num} tabular-nums`}>
                    {formatCurrency(p.retail_price)}
                  </td>
                  <td className={`${styles.num} tabular-nums`}>
                    {formatCurrency(p.wholesale_price)}
                  </td>
                  <td className={`${styles.num} tabular-nums`}>
                    {formatPercent(p.gst_rate)}
                  </td>
                  <td>
                    <span className={p.is_active ? styles.active : styles.inactive}>
                      {p.is_active ? '● Active' : '○ Inactive'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className={styles.pagination}>
        <span>
          {total} product{total === 1 ? '' : 's'} · page {page} of {pageCount}
        </span>
        <div className={styles.pageButtons}>
          <button
            type="button"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            Previous
          </button>
          <button
            type="button"
            disabled={page >= pageCount}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
