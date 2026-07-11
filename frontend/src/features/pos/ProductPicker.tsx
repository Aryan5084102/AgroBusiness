'use client';

import { useState } from 'react';
import { useProducts } from '@/features/products/useProducts';
import { formatCurrency } from '@/lib/formatting/currency';
import styles from './ProductPicker.module.scss';

interface ProductPickerProps {
  onAdd: (productId: string, name: string) => void;
}

// Searchable product list; clicking (or Enter) adds the product to the cart.
export function ProductPicker({ onAdd }: ProductPickerProps) {
  const [search, setSearch] = useState('');
  const { data, isLoading } = useProducts({ search: search || undefined, limit: 12 });
  const items = data?.items ?? [];

  return (
    <div className={styles.picker}>
      <input
        type="search"
        className={styles.search}
        placeholder="Search product by name, SKU or barcode…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        aria-label="Search products to add"
        autoFocus
      />
      <ul role="list" className={styles.results}>
        {isLoading ? (
          <li className={styles.muted}>Searching…</li>
        ) : items.length === 0 ? (
          <li className={styles.muted}>No matching products.</li>
        ) : (
          items.map((p) => (
            <li key={p.id}>
              <button
                type="button"
                className={styles.result}
                onClick={() => onAdd(p.id, p.name)}
              >
                <span className={styles.name}>{p.name}</span>
                <span className={styles.sku}>{p.sku}</span>
                <span className={`${styles.price} tabular-nums`}>
                  {formatCurrency(p.retail_price)}
                </span>
              </button>
            </li>
          ))
        )}
      </ul>
    </div>
  );
}
