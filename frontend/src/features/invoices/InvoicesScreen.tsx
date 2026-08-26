'use client';

import Link from 'next/link';
import { useState } from 'react';
import { StatusBadge } from '@/components/ui/Badge';
import { Card, CardHeader } from '@/components/ui/Card';
import { DataTable } from '@/components/ui/DataTable';
import { Select } from '@/components/ui/Field';
import { Pagination } from '@/components/ui/Pagination';
import { QueryState } from '@/components/feedback/QueryState';
import { SearchInput, Toolbar, ToolbarSpacer } from '@/components/ui/Toolbar';
import { StatCard, StatGrid } from '@/components/ui/StatCard';
import { formatCurrency } from '@/lib/formatting/currency';
import { formatDate } from '@/lib/formatting/dates';
import { InvoiceDetailDialog } from './InvoiceDetailDialog';
import type { InvoiceListItem, PaymentStatus, SaleChannel } from './api';
import { useInvoices } from './useInvoices';
import styles from './InvoicesScreen.module.scss';

const PAGE_SIZE = 25;

/** Invoice history across both channels. Finalized invoices are immutable, so
 * this screen is read-only by design — corrections are new documents. */
export function InvoicesScreen() {
  const [channel, setChannel] = useState<SaleChannel | ''>('');
  const [status, setStatus] = useState<PaymentStatus | ''>('');
  const [search, setSearch] = useState('');
  const [offset, setOffset] = useState(0);
  const [openId, setOpenId] = useState<string | null>(null);

  const invoices = useInvoices({
    channel: channel || undefined,
    paymentStatus: status || undefined,
    search: search || undefined,
    limit: PAGE_SIZE,
    offset,
  });

  const rows = invoices.data?.items ?? [];
  const unpaid = rows.reduce((total, row) => total + Number(row.outstanding), 0);

  return (
    <>
      <StatGrid>
        <StatCard
          label="Invoices matched"
          icon="invoices"
          isLoading={invoices.isLoading}
          value={invoices.data?.total ?? 0}
          hint="Across the current filter"
        />
        <StatCard
          label="Value matched"
          icon="trendUp"
          tone="positive"
          isLoading={invoices.isLoading}
          value={formatCurrency(invoices.data?.total_value ?? '0')}
          hint="Total billed for the filtered set"
        />
        <StatCard
          label="Unpaid on this page"
          icon="collections"
          tone={unpaid > 0 ? 'warning' : 'default'}
          isLoading={invoices.isLoading}
          value={formatCurrency(unpaid)}
          hint="Still to be collected"
        />
      </StatGrid>

      <Card>
        <CardHeader
          title="Invoices"
          description="Newest first. Select an invoice to see its lines, taxes and pricing snapshot."
        />
        <Toolbar>
          <SearchInput
            value={search}
            onChange={(value) => {
              setSearch(value);
              setOffset(0);
            }}
            placeholder="Search by invoice number…"
          />
          <Select
            label="Channel"
            hideLabel
            value={channel}
            onChange={(event) => {
              setChannel(event.target.value as SaleChannel | '');
              setOffset(0);
            }}
          >
            <option value="">All channels</option>
            <option value="retail">Retail</option>
            <option value="wholesale">Wholesale</option>
          </Select>
          <Select
            label="Payment status"
            hideLabel
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as PaymentStatus | '');
              setOffset(0);
            }}
          >
            <option value="">Any status</option>
            <option value="paid">Paid</option>
            <option value="partial">Partly paid</option>
            <option value="credit">On credit</option>
          </Select>
          <ToolbarSpacer />
        </Toolbar>

        <QueryState
          isLoading={invoices.isLoading}
          error={invoices.error}
          onRetry={invoices.refetch}
          loadingHeight={280}
        >
          <DataTable<InvoiceListItem>
            rows={rows}
            rowKey={(row) => row.id}
            onRowClick={(row) => setOpenId(row.id)}
            emptyTitle="No invoices match"
            emptyDescription="Try a wider date range or clear the filters."
            columns={[
              {
                key: 'number',
                header: 'Invoice',
                render: (row) => (
                  <span className={styles.primaryCell}>
                    <span>{row.invoice_number}</span>
                    <span className={styles.muted}>{formatDate(row.invoice_date)}</span>
                  </span>
                ),
              },
              {
                key: 'customer',
                header: 'Customer',
                render: (row) => row.customer_name ?? 'Walk-in',
              },
              {
                key: 'channel',
                header: 'Channel',
                secondary: true,
                render: (row) => <StatusBadge status={row.channel} />,
              },
              {
                key: 'by',
                header: 'Billed by',
                secondary: true,
                render: (row) => row.created_by_name ?? '—',
              },
              {
                key: 'status',
                header: 'Payment',
                render: (row) => <StatusBadge status={row.payment_status} />,
              },
              {
                key: 'outstanding',
                header: 'Outstanding',
                numeric: true,
                secondary: true,
                render: (row) =>
                  Number(row.outstanding) > 0 ? (
                    <span className={styles.due}>{formatCurrency(row.outstanding)}</span>
                  ) : (
                    '—'
                  ),
              },
              {
                key: 'total',
                header: 'Total',
                numeric: true,
                render: (row) => <strong>{formatCurrency(row.grand_total)}</strong>,
              },
              {
                key: 'bill',
                header: '',
                // stopPropagation: the row itself opens the detail dialog, and
                // a click here means "give me the printable bill" instead.
                render: (row) => (
                  <Link
                    href={`/invoices/${row.id}/bill`}
                    className={styles.billLink}
                    onClick={(event) => event.stopPropagation()}
                  >
                    Bill
                  </Link>
                ),
              },
            ]}
          />
        </QueryState>

        <Pagination
          total={invoices.data?.total ?? 0}
          limit={PAGE_SIZE}
          offset={offset}
          onOffsetChange={setOffset}
          noun="invoices"
        />
      </Card>

      <InvoiceDetailDialog invoiceId={openId} onClose={() => setOpenId(null)} />
    </>
  );
}
