'use client';

import { useRouter } from 'next/navigation';
import { StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { DataTable } from '@/components/ui/DataTable';
import { Modal } from '@/components/ui/Modal';
import { QueryState } from '@/components/feedback/QueryState';
import { formatCurrency, formatPercent } from '@/lib/formatting/currency';
import { formatDate, formatQuantity } from '@/lib/formatting/dates';
import type { InvoiceItem } from './api';
import { useInvoice } from './useInvoices';
import styles from './InvoicesScreen.module.scss';

interface InvoiceDetailDialogProps {
  invoiceId: string | null;
  onClose: () => void;
}

/** Read-only invoice view with its per-line pricing snapshot — the internal
 * view, including how each price was resolved. The customer-facing document
 * lives at `/invoices/:id/bill`, which prints on its own without the app
 * chrome around it. */
export function InvoiceDetailDialog({ invoiceId, onClose }: InvoiceDetailDialogProps) {
  const router = useRouter();
  const invoice = useInvoice(invoiceId);
  const detail = invoice.data;

  return (
    <Modal
      open={Boolean(invoiceId)}
      onClose={onClose}
      size="lg"
      title={detail ? `Invoice ${detail.invoice_number}` : 'Invoice'}
      description={
        detail
          ? `${detail.customer_name ?? 'Walk-in customer'} · ${formatDate(detail.invoice_date)}`
          : undefined
      }
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
          <Button
            variant="secondary"
            icon="print"
            disabled={!invoiceId}
            onClick={() => router.push(`/invoices/${invoiceId}/bill`)}
          >
            Open bill
          </Button>
        </>
      }
    >
      <QueryState
        isLoading={invoice.isLoading}
        error={invoice.error}
        onRetry={invoice.refetch}
      >
        {detail ? (
          <div className={styles.detail}>
            <dl className={styles.facts}>
              <div>
                <dt>Channel</dt>
                <dd>
                  <StatusBadge status={detail.channel} />
                </dd>
              </div>
              <div>
                <dt>Payment</dt>
                <dd>
                  <StatusBadge status={detail.payment_status} />
                </dd>
              </div>
              <div>
                <dt>Warehouse</dt>
                <dd>{detail.warehouse_name}</dd>
              </div>
              <div>
                <dt>Billed by</dt>
                <dd>{detail.created_by_name ?? '—'}</dd>
              </div>
            </dl>

            <DataTable<InvoiceItem>
              rows={detail.items}
              rowKey={(row) => `${row.product_id}-${row.unit_price}-${row.base_quantity}`}
              emptyTitle="This invoice has no lines"
              columns={[
                {
                  key: 'product',
                  header: 'Item',
                  render: (row) => (
                    <span className={styles.primaryCell}>
                      <span>{row.product_name}</span>
                      <span className={styles.muted}>
                        {row.sku} · priced from {row.price_source.replace(/_/g, ' ')}
                      </span>
                    </span>
                  ),
                },
                {
                  key: 'qty',
                  header: 'Qty',
                  numeric: true,
                  render: (row) => formatQuantity(row.base_quantity),
                },
                {
                  key: 'rate',
                  header: 'Rate',
                  numeric: true,
                  render: (row) => formatCurrency(row.unit_price),
                },
                {
                  key: 'taxable',
                  header: 'Taxable',
                  numeric: true,
                  secondary: true,
                  render: (row) => formatCurrency(row.taxable_value),
                },
                {
                  key: 'gst',
                  header: 'GST',
                  numeric: true,
                  secondary: true,
                  render: (row) => (
                    <span>
                      {formatCurrency(row.tax_amount)}
                      <span className={styles.muted}>
                        {' '}
                        ({formatPercent(row.gst_rate)})
                      </span>
                    </span>
                  ),
                },
                {
                  key: 'total',
                  header: 'Amount',
                  numeric: true,
                  render: (row) => <strong>{formatCurrency(row.line_total)}</strong>,
                },
              ]}
            />

            <dl className={styles.totals}>
              <div>
                <dt>Taxable value</dt>
                <dd className="tabular-nums">{formatCurrency(detail.subtotal)}</dd>
              </div>
              {Number(detail.discount_total) > 0 ? (
                <div>
                  <dt>Discount</dt>
                  <dd className="tabular-nums">
                    −{formatCurrency(detail.discount_total)}
                  </dd>
                </div>
              ) : null}
              <div>
                <dt>GST</dt>
                <dd className="tabular-nums">{formatCurrency(detail.tax_total)}</dd>
              </div>
              <div className={styles.grand}>
                <dt>Invoice total</dt>
                <dd className="tabular-nums">{formatCurrency(detail.grand_total)}</dd>
              </div>
              <div>
                <dt>Paid</dt>
                <dd className="tabular-nums">{formatCurrency(detail.paid_amount)}</dd>
              </div>
              {Number(detail.outstanding) > 0 ? (
                <div className={styles.due}>
                  <dt>Outstanding</dt>
                  <dd className="tabular-nums">{formatCurrency(detail.outstanding)}</dd>
                </div>
              ) : null}
            </dl>
          </div>
        ) : null}
      </QueryState>
    </Modal>
  );
}
