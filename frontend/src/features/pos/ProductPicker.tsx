'use client';

import { useState } from 'react';
import { Icon } from '@/components/ui/Icon';
import { Input } from '@/components/ui/Field';
import { Skeleton } from '@/components/ui/Skeleton';
import { useProducts } from '@/features/products/useProducts';
import { formatCurrency } from '@/lib/formatting/currency';
import { formatQuantity } from '@/lib/formatting/dates';
import styles from './ProductPicker.module.scss';

interface ProductPickerProps {
  onAdd: (productId: string, name: string) => void;
  /** Show wholesale rather than retail prices (used by the order builder). */
  wholesale?: boolean;
}

/** Searchable product list. Clicking (or pressing Enter on) a row adds it. */
export function ProductPicker({ onAdd, wholesale = false }: ProductPickerProps) {
  const [search, setSearch] = useState('');
  const { data, isLoading } = useProducts({
    search: search || undefined,
    activeOnly: true,
    limit: 12,
  });
  const items = data?.items ?? [];

  return (
    <div className={styles.picker}>
      <Input
        label="Search products"
        hideLabel
        type="search"
        value={search}
        placeholder="Search by name, SKU or barcode…"
        prefix={<Icon name="search" size={16} />}
        autoFocus
        onChange={(event) => setSearch(event.target.value)}
      />

      {isLoading ? (
        <div className={styles.loading}>
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} height={46} />
          ))}
        </div>
      ) : items.length === 0 ? (
        <p className={styles.muted}>
          {search ? 'No product matches that search.' : 'No active products yet.'}
        </p>
      ) : (
        <ul role="list" className={styles.results}>
          {items.map((product) => {
            const outOfStock = Number(product.on_hand) <= 0;
            return (
              <li key={product.id}>
                <button
                  type="button"
                  className={styles.result}
                  disabled={outOfStock}
                  onClick={() => onAdd(product.id, product.name)}
                >
                  <span className={styles.info}>
                    <span className={styles.name}>{product.name}</span>
                    <span className={styles.meta}>
                      {product.sku}
                      {outOfStock ? (
                        <span className={styles.out}> · out of stock</span>
                      ) : (
                        ` · ${formatQuantity(product.on_hand)} ${product.unit_code ?? ''} in stock`
                      )}
                    </span>
                  </span>
                  <span className={`${styles.price} tabular-nums`}>
                    {formatCurrency(
                      wholesale ? product.wholesale_price : product.retail_price,
                    )}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
