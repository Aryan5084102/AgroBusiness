'use client';

import { useState } from 'react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { DataTable } from '@/components/ui/DataTable';
import { Select } from '@/components/ui/Field';
import { Pagination } from '@/components/ui/Pagination';
import { QueryState } from '@/components/feedback/QueryState';
import { SearchInput, Toolbar, ToolbarSpacer } from '@/components/ui/Toolbar';
import { usePermissions } from '@/features/auth/usePermissions';
import { formatCurrency, formatPercent } from '@/lib/formatting/currency';
import { formatQuantity } from '@/lib/formatting/dates';
import { ProductDialog } from './ProductDialog';
import type { Product } from './api';
import { useCategories, useProducts } from './useProducts';
import styles from './ProductsTable.module.scss';

const PAGE_SIZE = 25;

/** The catalogue: search, filter by category, and (with permission) add or
 * edit a product. Prices here apply to future sales only — finalized invoices
 * keep their own snapshot. */
export function ProductsTable() {
  const { can } = usePermissions();
  const [search, setSearch] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [offset, setOffset] = useState(0);
  const [editing, setEditing] = useState<Product | null>(null);
  const [creating, setCreating] = useState(false);

  const categories = useCategories();
  const products = useProducts({
    search: search || undefined,
    categoryId: categoryId || undefined,
    limit: PAGE_SIZE,
    offset,
  });

  const canEdit = can('product.update');
  const canCreate = can('product.create');

  return (
    <>
      <Card>
        <CardHeader
          title="Catalogue"
          description="Everything you buy and sell, with its selling prices, tax rate and reorder level."
          actions={
            canCreate ? (
              <Button size="sm" icon="plus" onClick={() => setCreating(true)}>
                Add product
              </Button>
            ) : null
          }
        />
        <Toolbar>
          <SearchInput
            value={search}
            onChange={(value) => {
              setSearch(value);
              setOffset(0);
            }}
            placeholder="Search by name, SKU or barcode…"
          />
          <Select
            label="Category"
            hideLabel
            value={categoryId}
            onChange={(event) => {
              setCategoryId(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">All categories</option>
            {(categories.data ?? []).map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </Select>
          <ToolbarSpacer />
        </Toolbar>

        <QueryState
          isLoading={products.isLoading}
          error={products.error}
          onRetry={products.refetch}
          loadingHeight={280}
        >
          <DataTable<Product>
            rows={products.data?.items ?? []}
            rowKey={(row) => row.id}
            onRowClick={canEdit ? (row) => setEditing(row) : undefined}
            emptyTitle="No products found"
            emptyDescription={
              search
                ? 'Nothing matches that search. Try a different name or SKU.'
                : 'Add your first product to start selling.'
            }
            emptyAction={
              canCreate && !search ? (
                <Button size="sm" icon="plus" onClick={() => setCreating(true)}>
                  Add product
                </Button>
              ) : null
            }
            columns={[
              {
                key: 'name',
                header: 'Product',
                render: (row) => (
                  <span className={styles.primaryCell}>
                    <span>{row.name}</span>
                    <span className={styles.muted}>
                      {row.sku}
                      {row.category_name ? ` · ${row.category_name}` : ''}
                    </span>
                  </span>
                ),
              },
              {
                key: 'stock',
                header: 'In stock',
                numeric: true,
                render: (row) => (
                  <span
                    className={
                      Number(row.min_stock) > 0 &&
                      Number(row.on_hand) < Number(row.min_stock)
                        ? styles.low
                        : undefined
                    }
                  >
                    {formatQuantity(row.on_hand)} {row.unit_code ?? ''}
                  </span>
                ),
              },
              {
                key: 'retail',
                header: 'Retail',
                numeric: true,
                render: (row) => formatCurrency(row.retail_price),
              },
              {
                key: 'wholesale',
                header: 'Wholesale',
                numeric: true,
                secondary: true,
                render: (row) => formatCurrency(row.wholesale_price),
              },
              {
                key: 'gst',
                header: 'GST',
                numeric: true,
                secondary: true,
                render: (row) => formatPercent(row.gst_rate),
              },
              {
                key: 'status',
                header: 'Status',
                render: (row) =>
                  row.is_active ? (
                    <Badge tone="success" dot>
                      Active
                    </Badge>
                  ) : (
                    <Badge tone="neutral" dot>
                      Inactive
                    </Badge>
                  ),
              },
            ]}
          />
        </QueryState>

        <Pagination
          total={products.data?.total ?? 0}
          limit={PAGE_SIZE}
          offset={offset}
          onOffsetChange={setOffset}
          noun="products"
        />
      </Card>

      <ProductDialog open={creating} product={null} onClose={() => setCreating(false)} />
      <ProductDialog
        open={Boolean(editing)}
        product={editing}
        onClose={() => setEditing(null)}
      />
    </>
  );
}
