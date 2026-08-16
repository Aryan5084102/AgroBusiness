'use client';

import Link from 'next/link';
import { Badge, StatusBadge } from '@/components/ui/Badge';
import { BarChart } from '@/components/ui/BarChart';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { QueryState } from '@/components/feedback/QueryState';
import { StatCard, StatGrid } from '@/components/ui/StatCard';
import { useMe } from '@/features/auth/useAuth';
import { usePermissions } from '@/features/auth/usePermissions';
import { useInvoices } from '@/features/invoices/useInvoices';
import { useStock } from '@/features/inventory/useInventory';
import { useJobs } from '@/features/service/useService';
import { useReceivables } from '@/features/collections/useCollections';
import { useSalesTrend, useTopProducts } from '@/features/reports/useReports';
import { formatCurrency } from '@/lib/formatting/currency';
import { formatQuantity, formatShortDate } from '@/lib/formatting/dates';
import type { InvoiceListItem } from '@/features/invoices/api';
import type { StockRow } from '@/features/inventory/api';
import type { RepairJob } from '@/features/service/api';
import type { ReceivableRow } from '@/features/collections/api';
import { useDashboard } from './useDashboard';
import styles from './DashboardScreen.module.scss';

/**
 * The home screen every role lands on. Each panel is gated by the permission
 * that backs its endpoint, so a billing operator, a technician and the owner
 * all get a working dashboard made of exactly the panels they are allowed to
 * see — no empty shell, and no request that would 403.
 */
export function DashboardScreen() {
  const { can } = usePermissions();
  const { data: user } = useMe();

  const canReport = can('report.view');
  const canStock = can('inventory.view');
  const canService = can('service.manage');
  const canCollect = can('payment.receive');
  const canSell = can('sales.create');

  const summary = useDashboard(canReport);
  const trend = useSalesTrend(14, canReport);
  const topProducts = useTopProducts(30, canReport);
  const lowStock = useStock({ lowOnly: true, limit: 6 }, canStock);
  const jobs = useJobs({ limit: 6 }, canService);
  const receivables = useReceivables(canCollect);
  const recentInvoices = useInvoices({ limit: 6 }, canSell);

  const firstName = (user?.full_name ?? '').split(' ')[0];

  return (
    <div className={styles.dashboard}>
      <p className={styles.greeting}>
        Welcome back{firstName ? `, ${firstName}` : ''}. Here is what needs you today.
      </p>

      {canReport ? (
        <StatGrid>
          <StatCard
            label="Sales today"
            icon="trendUp"
            tone="positive"
            isLoading={summary.isLoading}
            value={formatCurrency(summary.data?.sales_today_total ?? '0')}
            hint={`Retail ${formatCurrency(summary.data?.retail_today_total ?? '0')} · Wholesale ${formatCurrency(summary.data?.wholesale_today_total ?? '0')}`}
          />
          <StatCard
            label="Collected today"
            icon="collections"
            isLoading={summary.isLoading}
            value={formatCurrency(summary.data?.collected_today_total ?? '0')}
            hint="Payments received across all methods"
          />
          <StatCard
            label="Receivables"
            icon="customers"
            tone="warning"
            isLoading={summary.isLoading}
            value={formatCurrency(summary.data?.receivables_outstanding ?? '0')}
            hint="Outstanding on unpaid invoices"
          />
          <StatCard
            label="Low stock"
            icon="alert"
            tone={(summary.data?.low_stock_product_count ?? 0) > 0 ? 'danger' : 'default'}
            isLoading={summary.isLoading}
            value={summary.data?.low_stock_product_count ?? 0}
            hint="Products below their reorder level"
          />
        </StatGrid>
      ) : null}

      <div className={styles.grid}>
        {canReport ? (
          <Card>
            <CardHeader
              title="Revenue, last 14 days"
              description="Invoice value per day across retail and wholesale."
            />
            <CardBody>
              <QueryState
                isLoading={trend.isLoading}
                error={trend.error}
                onRetry={trend.refetch}
                loadingHeight={140}
              >
                <BarChart
                  points={(trend.data ?? []).map((point) => ({
                    label: formatShortDate(point.day),
                    value: Number(point.revenue),
                    title: `${formatShortDate(point.day)}: ${formatCurrency(point.revenue)} across ${point.invoice_count} invoice(s)`,
                  }))}
                />
              </QueryState>
            </CardBody>
          </Card>
        ) : null}

        {canReport ? (
          <Card>
            <CardHeader
              title="Best sellers"
              description="By revenue over the last 30 days."
            />
            <QueryState
              isLoading={topProducts.isLoading}
              error={topProducts.error}
              onRetry={topProducts.refetch}
            >
              <DataTable
                rows={topProducts.data ?? []}
                rowKey={(row) => row.product_id}
                emptyTitle="No sales in this period"
                emptyDescription="Once invoices are raised, your best sellers appear here."
                columns={[
                  {
                    key: 'name',
                    header: 'Product',
                    render: (row) => (
                      <span className={styles.primaryCell}>
                        <span>{row.product_name}</span>
                        <span className={styles.muted}>{row.sku}</span>
                      </span>
                    ),
                  },
                  {
                    key: 'qty',
                    header: 'Sold',
                    numeric: true,
                    secondary: true,
                    render: (row) => formatQuantity(row.quantity_sold),
                  },
                  {
                    key: 'revenue',
                    header: 'Revenue',
                    numeric: true,
                    render: (row) => formatCurrency(row.revenue),
                  },
                ]}
              />
            </QueryState>
          </Card>
        ) : null}

        {canStock ? (
          <Card>
            <CardHeader
              title="Needs reordering"
              description="Stock at or below the minimum level."
              actions={
                <Link href="/inventory">
                  <Button variant="ghost" size="sm">
                    Open inventory
                  </Button>
                </Link>
              }
            />
            <QueryState
              isLoading={lowStock.isLoading}
              error={lowStock.error}
              onRetry={lowStock.refetch}
            >
              <DataTable<StockRow>
                rows={lowStock.data?.items ?? []}
                rowKey={(row) => `${row.product_id}-${row.warehouse_id}`}
                emptyTitle="Everything is above its minimum"
                emptyDescription="No product has fallen below its reorder level."
                columns={[
                  {
                    key: 'name',
                    header: 'Product',
                    render: (row) => (
                      <span className={styles.primaryCell}>
                        <span>{row.product_name}</span>
                        <span className={styles.muted}>{row.warehouse_name}</span>
                      </span>
                    ),
                  },
                  {
                    key: 'onHand',
                    header: 'On hand',
                    numeric: true,
                    render: (row) => (
                      <span className={styles.lowValue}>
                        {formatQuantity(row.on_hand)} {row.unit_code}
                      </span>
                    ),
                  },
                  {
                    key: 'min',
                    header: 'Minimum',
                    numeric: true,
                    secondary: true,
                    render: (row) => formatQuantity(row.min_stock),
                  },
                ]}
              />
            </QueryState>
          </Card>
        ) : null}

        {canService ? (
          <Card>
            <CardHeader
              title="Workshop"
              description="Repair jobs currently on the bench."
              actions={
                <Link href="/service">
                  <Button variant="ghost" size="sm">
                    All jobs
                  </Button>
                </Link>
              }
            />
            <QueryState
              isLoading={jobs.isLoading}
              error={jobs.error}
              onRetry={jobs.refetch}
            >
              <DataTable<RepairJob>
                rows={jobs.data?.items ?? []}
                rowKey={(row) => row.id}
                emptyTitle="No repair jobs yet"
                emptyDescription="Machines booked in for service will appear here."
                columns={[
                  {
                    key: 'job',
                    header: 'Job',
                    render: (row) => (
                      <span className={styles.primaryCell}>
                        <span>{row.job_number}</span>
                        <span className={styles.muted}>
                          {row.product_name ?? 'Unspecified machine'}
                        </span>
                      </span>
                    ),
                  },
                  {
                    key: 'customer',
                    header: 'Customer',
                    secondary: true,
                    render: (row) => row.customer_name ?? '—',
                  },
                  {
                    key: 'status',
                    header: 'Status',
                    render: (row) => <StatusBadge status={row.status} />,
                  },
                ]}
              />
            </QueryState>
          </Card>
        ) : null}

        {canCollect ? (
          <Card>
            <CardHeader
              title="Money to collect"
              description="Customers with an open balance, largest first."
              actions={
                <Link href="/collections">
                  <Button variant="ghost" size="sm">
                    Collect
                  </Button>
                </Link>
              }
            />
            <QueryState
              isLoading={receivables.isLoading}
              error={receivables.error}
              onRetry={receivables.refetch}
            >
              <DataTable<ReceivableRow>
                rows={(receivables.data?.rows ?? []).slice(0, 6)}
                rowKey={(row) => row.customer_id}
                emptyTitle="Nothing outstanding"
                emptyDescription="Every invoice has been settled."
                columns={[
                  {
                    key: 'customer',
                    header: 'Customer',
                    render: (row) => (
                      <span className={styles.primaryCell}>
                        <span>{row.customer_name}</span>
                        <span className={styles.muted}>
                          {row.open_invoices} open invoice(s)
                        </span>
                      </span>
                    ),
                  },
                  {
                    key: 'age',
                    header: 'Oldest',
                    secondary: true,
                    render: (row) =>
                      row.days_overdue > 0 ? (
                        <Badge tone={row.days_overdue > 30 ? 'danger' : 'warning'}>
                          {row.days_overdue} days
                        </Badge>
                      ) : (
                        '—'
                      ),
                  },
                  {
                    key: 'amount',
                    header: 'Outstanding',
                    numeric: true,
                    render: (row) => formatCurrency(row.outstanding),
                  },
                ]}
              />
            </QueryState>
          </Card>
        ) : null}

        {canSell ? (
          <Card>
            <CardHeader
              title="Latest invoices"
              description="The most recent sales across both channels."
              actions={
                <Link href="/invoices">
                  <Button variant="ghost" size="sm">
                    All invoices
                  </Button>
                </Link>
              }
            />
            <QueryState
              isLoading={recentInvoices.isLoading}
              error={recentInvoices.error}
              onRetry={recentInvoices.refetch}
            >
              <DataTable<InvoiceListItem>
                rows={recentInvoices.data?.items ?? []}
                rowKey={(row) => row.id}
                emptyTitle="No invoices yet"
                emptyDescription="Sales you finalize at the counter show up here."
                columns={invoiceColumns}
              />
            </QueryState>
          </Card>
        ) : null}
      </div>
    </div>
  );
}

const invoiceColumns: Column<InvoiceListItem>[] = [
  {
    key: 'number',
    header: 'Invoice',
    render: (row) => (
      <span className={styles.primaryCell}>
        <span>{row.invoice_number}</span>
        <span className={styles.muted}>{row.customer_name ?? 'Walk-in'}</span>
      </span>
    ),
  },
  {
    key: 'date',
    header: 'Date',
    secondary: true,
    render: (row) => formatShortDate(row.invoice_date),
  },
  {
    key: 'status',
    header: 'Status',
    render: (row) => <StatusBadge status={row.payment_status} />,
  },
  {
    key: 'total',
    header: 'Total',
    numeric: true,
    render: (row) => formatCurrency(row.grand_total),
  },
];
