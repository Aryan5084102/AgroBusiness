'use client';

import { useState } from 'react';
import { Badge, humanize } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { DataTable } from '@/components/ui/DataTable';
import { QueryState } from '@/components/feedback/QueryState';
import { SearchInput, Toolbar, ToolbarSpacer } from '@/components/ui/Toolbar';
import { StatCard, StatGrid } from '@/components/ui/StatCard';
import { usePermissions } from '@/features/auth/usePermissions';
import { formatCurrency } from '@/lib/formatting/currency';
import { CustomerDialog } from './CustomerDialog';
import type { Customer } from './api';
import { useCustomers } from './useCustomers';
import styles from './CustomersPanel.module.scss';

/** Customer book with live credit exposure. Clicking a row opens their details
 * so a dealer's limit can be adjusted without leaving the list. */
export function CustomersPanel() {
  const { can } = usePermissions();
  const [search, setSearch] = useState('');
  const [editing, setEditing] = useState<Customer | null>(null);
  const [creating, setCreating] = useState(false);

  const customers = useCustomers({ search: search || undefined });
  const rows = customers.data ?? [];
  const canCreate = can('customer.create');

  const totalOutstanding = rows.reduce((sum, row) => sum + Number(row.outstanding), 0);
  const overLimit = rows.filter((row) => Number(row.available_credit) < 0).length;

  return (
    <>
      <StatGrid>
        <StatCard
          label="Customers"
          icon="customers"
          isLoading={customers.isLoading}
          value={rows.length}
          hint="Matching the current search"
        />
        <StatCard
          label="Total outstanding"
          icon="collections"
          tone={totalOutstanding > 0 ? 'warning' : 'default'}
          isLoading={customers.isLoading}
          value={formatCurrency(totalOutstanding)}
          hint="Owed across all listed customers"
        />
        <StatCard
          label="Over their limit"
          icon="alert"
          tone={overLimit > 0 ? 'danger' : 'positive'}
          isLoading={customers.isLoading}
          value={overLimit}
          hint="Further credit sales need an override"
        />
      </StatGrid>

      <Card>
        <CardHeader
          title="Customers & dealers"
          description="Walk-ins, farmers, retailers and dealers. Credit limits are enforced when a wholesale order is confirmed."
          actions={
            canCreate ? (
              <Button size="sm" icon="plus" onClick={() => setCreating(true)}>
                Add customer
              </Button>
            ) : null
          }
        />
        <Toolbar>
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search by name or code…"
          />
          <ToolbarSpacer />
        </Toolbar>

        <QueryState
          isLoading={customers.isLoading}
          error={customers.error}
          onRetry={customers.refetch}
          loadingHeight={280}
        >
          <DataTable<Customer>
            rows={rows}
            rowKey={(row) => row.id}
            onRowClick={canCreate ? (row) => setEditing(row) : undefined}
            emptyTitle="No customers found"
            emptyDescription={
              search
                ? 'Nothing matches that search.'
                : 'Add a customer to sell on credit and track their balance.'
            }
            emptyAction={
              canCreate && !search ? (
                <Button size="sm" icon="plus" onClick={() => setCreating(true)}>
                  Add customer
                </Button>
              ) : null
            }
            columns={[
              {
                key: 'name',
                header: 'Customer',
                render: (row) => (
                  <span className={styles.primaryCell}>
                    <span>{row.name}</span>
                    <span className={styles.muted}>
                      {row.code}
                      {row.phone ? ` · ${row.phone}` : ''}
                    </span>
                  </span>
                ),
              },
              {
                key: 'type',
                header: 'Type',
                render: (row) => (
                  <Badge tone="neutral">{humanize(row.customer_type)}</Badge>
                ),
              },
              {
                key: 'limit',
                header: 'Credit limit',
                numeric: true,
                secondary: true,
                render: (row) =>
                  Number(row.credit_limit) > 0 ? formatCurrency(row.credit_limit) : '—',
              },
              {
                key: 'outstanding',
                header: 'Outstanding',
                numeric: true,
                render: (row) =>
                  Number(row.outstanding) > 0 ? (
                    <span className={styles.due}>{formatCurrency(row.outstanding)}</span>
                  ) : (
                    '—'
                  ),
              },
              {
                key: 'available',
                header: 'Credit left',
                numeric: true,
                render: (row) =>
                  Number(row.credit_limit) > 0 ? (
                    <span
                      className={
                        Number(row.available_credit) < 0 ? styles.negative : undefined
                      }
                    >
                      {formatCurrency(row.available_credit)}
                    </span>
                  ) : (
                    <span className={styles.muted}>Cash only</span>
                  ),
              },
              {
                key: 'status',
                header: 'Status',
                secondary: true,
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
      </Card>

      <CustomerDialog
        open={creating}
        customer={null}
        onClose={() => setCreating(false)}
      />
      <CustomerDialog
        open={Boolean(editing)}
        customer={editing}
        onClose={() => setEditing(null)}
      />
    </>
  );
}
