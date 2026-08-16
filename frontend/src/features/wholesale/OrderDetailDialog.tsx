'use client';

import { StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { DataTable } from '@/components/ui/DataTable';
import { Modal } from '@/components/ui/Modal';
import { QueryState } from '@/components/feedback/QueryState';
import { useOrder } from '@/features/invoices/useInvoices';
import type { OrderItem } from '@/features/invoices/api';
import { formatCurrency, formatPercent } from '@/lib/formatting/currency';
import { formatDate, formatQuantity } from '@/lib/formatting/dates';
import styles from './WholesaleScreen.module.scss';

interface OrderDetailDialogProps {
  orderId: string | null;
  onClose: () => void;
}

/** Read-only order view showing ordered / reserved / dispatched per line, so
 * it is obvious what stock is committed and what has actually left. */
export function OrderDetailDialog({ orderId, onClose }: OrderDetailDialogProps) {
  const order = useOrder(orderId);
  const detail = order.data;

  return (
    <Modal
      open={Boolean(orderId)}
      onClose={onClose}
      size="lg"
      title={detail ? `Order ${detail.order_number}` : 'Order'}
      description={
        detail ? `${detail.customer_name} · ${formatDate(detail.order_date)}` : undefined
      }
      footer={
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      }
    >
      <QueryState isLoading={order.isLoading} error={order.error} onRetry={order.refetch}>
        {detail ? (
          <div className={styles.detail}>
            <dl className={styles.facts}>
              <div>
                <dt>Status</dt>
                <dd>
                  <StatusBadge status={detail.status} />
                </dd>
              </div>
              <div>
                <dt>Warehouse</dt>
                <dd>{detail.warehouse_name}</dd>
              </div>
              <div>
                <dt>Credit override</dt>
                <dd>{detail.credit_override_approved ? 'Approved' : 'Not needed'}</dd>
              </div>
              <div>
                <dt>Invoice</dt>
                <dd>{detail.sales_invoice_id ? 'Raised' : 'Not yet raised'}</dd>
              </div>
            </dl>

            <DataTable<OrderItem>
              rows={detail.items}
              rowKey={(row) => row.product_id}
              emptyTitle="This order has no lines"
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
                  key: 'ordered',
                  header: 'Ordered',
                  numeric: true,
                  render: (row) => formatQuantity(row.base_quantity),
                },
                {
                  key: 'reserved',
                  header: 'Reserved',
                  numeric: true,
                  secondary: true,
                  render: (row) => formatQuantity(row.reserved_quantity),
                },
                {
                  key: 'dispatched',
                  header: 'Dispatched',
                  numeric: true,
                  secondary: true,
                  render: (row) => formatQuantity(row.dispatched_quantity),
                },
                {
                  key: 'rate',
                  header: 'Rate',
                  numeric: true,
                  render: (row) => formatCurrency(row.unit_price),
                },
                {
                  key: 'gst',
                  header: 'GST',
                  numeric: true,
                  secondary: true,
                  render: (row) => formatPercent(row.gst_rate),
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
              <div>
                <dt>GST</dt>
                <dd className="tabular-nums">{formatCurrency(detail.tax_total)}</dd>
              </div>
              <div className={styles.grand}>
                <dt>Order value</dt>
                <dd className="tabular-nums">{formatCurrency(detail.grand_total)}</dd>
              </div>
            </dl>
          </div>
        ) : null}
      </QueryState>
    </Modal>
  );
}
