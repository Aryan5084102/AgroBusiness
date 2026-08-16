'use client';

import { Button } from '@/components/ui/Button';
import { DataTable } from '@/components/ui/DataTable';
import { Modal } from '@/components/ui/Modal';
import { QueryState } from '@/components/feedback/QueryState';
import { useReceipt } from '@/features/invoices/useInvoices';
import type { ReceiptItem } from '@/features/invoices/api';
import { formatCurrency } from '@/lib/formatting/currency';
import { formatDate, formatQuantity } from '@/lib/formatting/dates';
import styles from './PurchasesScreen.module.scss';

interface ReceiptDetailDialogProps {
  receiptId: string | null;
  onClose: () => void;
}

/** Shows what arrived and the landed cost per unit — the supplier rate plus its
 * share of freight and other charges. */
export function ReceiptDetailDialog({ receiptId, onClose }: ReceiptDetailDialogProps) {
  const receipt = useReceipt(receiptId);
  const detail = receipt.data;

  return (
    <Modal
      open={Boolean(receiptId)}
      onClose={onClose}
      size="lg"
      title={detail ? `Receipt ${detail.grn_number}` : 'Goods receipt'}
      description={
        detail
          ? `${detail.supplier_name} · ${formatDate(detail.receipt_date)} · into ${detail.warehouse_name}`
          : undefined
      }
      footer={
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      }
    >
      <QueryState
        isLoading={receipt.isLoading}
        error={receipt.error}
        onRetry={receipt.refetch}
      >
        {detail ? (
          <DataTable<ReceiptItem>
            rows={detail.items}
            rowKey={(row) => row.product_id}
            emptyTitle="This receipt has no lines"
            columns={[
              {
                key: 'product',
                header: 'Item',
                render: (row) => (
                  <span className={styles.primaryCell}>
                    <span>{row.product_name}</span>
                    <span className={styles.muted}>{row.sku}</span>
                  </span>
                ),
              },
              {
                key: 'qty',
                header: 'Received',
                numeric: true,
                render: (row) => formatQuantity(row.received_base_quantity),
              },
              {
                key: 'free',
                header: 'Free',
                numeric: true,
                secondary: true,
                render: (row) =>
                  Number(row.free_base_quantity) > 0
                    ? formatQuantity(row.free_base_quantity)
                    : '—',
              },
              {
                key: 'rate',
                header: 'Rate',
                numeric: true,
                render: (row) => formatCurrency(row.unit_rate),
              },
              {
                key: 'landed',
                header: 'Landed cost',
                numeric: true,
                render: (row) => <strong>{formatCurrency(row.landed_unit_cost)}</strong>,
              },
              {
                key: 'value',
                header: 'Line value',
                numeric: true,
                secondary: true,
                render: (row) => formatCurrency(row.line_value),
              },
            ]}
          />
        ) : null}
      </QueryState>
    </Modal>
  );
}
