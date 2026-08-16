'use client';

import { useState } from 'react';
import { Card, CardHeader } from '@/components/ui/Card';
import { DataTable } from '@/components/ui/DataTable';
import { Pagination } from '@/components/ui/Pagination';
import { QueryState } from '@/components/feedback/QueryState';
import { SearchInput, Toolbar, ToolbarSpacer } from '@/components/ui/Toolbar';
import { Tabs } from '@/components/ui/Tabs';
import { usePermissions } from '@/features/auth/usePermissions';
import { GoodsReceiptScreen } from '@/features/goods-receipt/GoodsReceiptScreen';
import { SuppliersPanel } from '@/features/suppliers/SuppliersPanel';
import { useReceipts } from '@/features/invoices/useInvoices';
import type { ReceiptListItem } from '@/features/invoices/api';
import { formatCurrency } from '@/lib/formatting/currency';
import { formatDate } from '@/lib/formatting/dates';
import { ReceiptDetailDialog } from './ReceiptDetailDialog';
import styles from './PurchasesScreen.module.scss';

type Tab = 'receive' | 'history' | 'suppliers';

const PAGE_SIZE = 25;

/** Buying side: book stock in, review what has been received, and keep the
 * supplier list. Receiving is gated by `purchase.create`; viewing needs only
 * `purchase.view`, so an auditor can inspect without being able to post. */
export function PurchasesScreen() {
  const { can } = usePermissions();
  const canReceive = can('purchase.create');
  const [tab, setTab] = useState<Tab>(canReceive ? 'receive' : 'history');

  const tabs = [
    ...(canReceive
      ? [{ id: 'receive' as const, label: 'Receive stock', icon: 'plus' as const }]
      : []),
    { id: 'history' as const, label: 'Receipt history', icon: 'purchases' as const },
    { id: 'suppliers' as const, label: 'Suppliers', icon: 'customers' as const },
  ];

  return (
    <>
      <Tabs<Tab> label="Purchases sections" active={tab} onChange={setTab} items={tabs} />
      {tab === 'receive' ? <GoodsReceiptScreen /> : null}
      {tab === 'history' ? <ReceiptHistory /> : null}
      {tab === 'suppliers' ? <SuppliersPanel /> : null}
    </>
  );
}

function ReceiptHistory() {
  const [search, setSearch] = useState('');
  const [offset, setOffset] = useState(0);
  const [openId, setOpenId] = useState<string | null>(null);
  const receipts = useReceipts({
    search: search || undefined,
    limit: PAGE_SIZE,
    offset,
  });

  return (
    <>
      <Card>
        <CardHeader
          title="Goods receipts"
          description="Every delivery booked in, newest first. Open one to see its landed costs."
        />
        <Toolbar>
          <SearchInput
            value={search}
            onChange={(value) => {
              setSearch(value);
              setOffset(0);
            }}
            placeholder="Search by GRN number…"
          />
          <ToolbarSpacer />
        </Toolbar>
        <QueryState
          isLoading={receipts.isLoading}
          error={receipts.error}
          onRetry={receipts.refetch}
          loadingHeight={260}
        >
          <DataTable<ReceiptListItem>
            rows={receipts.data?.items ?? []}
            rowKey={(row) => row.id}
            onRowClick={(row) => setOpenId(row.id)}
            emptyTitle="No goods received yet"
            emptyDescription="Book in your first delivery from the Receive stock tab."
            columns={[
              {
                key: 'grn',
                header: 'GRN',
                render: (row) => (
                  <span className={styles.primaryCell}>
                    <span>{row.grn_number}</span>
                    <span className={styles.muted}>{formatDate(row.receipt_date)}</span>
                  </span>
                ),
              },
              { key: 'supplier', header: 'Supplier', render: (row) => row.supplier_name },
              {
                key: 'warehouse',
                header: 'Into',
                secondary: true,
                render: (row) => row.warehouse_name,
              },
              {
                key: 'lines',
                header: 'Lines',
                numeric: true,
                secondary: true,
                render: (row) => row.line_count,
              },
              {
                key: 'value',
                header: 'Goods value',
                numeric: true,
                render: (row) => <strong>{formatCurrency(row.total_value)}</strong>,
              },
            ]}
          />
        </QueryState>
        <Pagination
          total={receipts.data?.total ?? 0}
          limit={PAGE_SIZE}
          offset={offset}
          onOffsetChange={setOffset}
          noun="receipts"
        />
      </Card>

      <ReceiptDetailDialog receiptId={openId} onClose={() => setOpenId(null)} />
    </>
  );
}
