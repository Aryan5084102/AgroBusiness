'use client';

import { useEffect, useState } from 'react';
import { Badge, StatusBadge, humanize } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { DataTable } from '@/components/ui/DataTable';
import { Input, Select } from '@/components/ui/Field';
import { QueryState } from '@/components/feedback/QueryState';
import { StatCard, StatGrid } from '@/components/ui/StatCard';
import { Tabs } from '@/components/ui/Tabs';
import { useToast } from '@/components/ui/Toast';
import { useCustomers } from '@/features/customers/useCustomers';
import type { PaymentMethod } from '@/features/pos/api';
import { ApiError } from '@/lib/api/client';
import { formatCurrency } from '@/lib/formatting/currency';
import { formatDate, formatDateTime } from '@/lib/formatting/dates';
import type { OutstandingInvoice, PaymentRecord, ReceivableRow } from './api';
import {
  useOutstanding,
  usePaymentHistory,
  useReceivables,
  useReceivePayment,
} from './useCollections';
import styles from './CollectionsScreen.module.scss';

type Tab = 'collect' | 'receivables' | 'history';

const METHODS: { value: PaymentMethod | 'bank_transfer' | 'cheque'; label: string }[] = [
  { value: 'cash', label: 'Cash' },
  { value: 'upi', label: 'UPI' },
  { value: 'card', label: 'Card' },
  { value: 'bank_transfer', label: 'Bank transfer' },
  { value: 'cheque', label: 'Cheque' },
];

/** Receiving money: pick the customer, see what they owe, take the payment.
 * The server allocates it FIFO across open invoices and posts the journal. */
export function CollectionsScreen() {
  const toast = useToast();
  const [tab, setTab] = useState<Tab>('collect');
  const [customerId, setCustomerId] = useState('');
  const [amount, setAmount] = useState('');
  const [method, setMethod] = useState<string>('cash');
  const [reference, setReference] = useState('');
  const [error, setError] = useState<string | null>(null);

  const customers = useCustomers();
  const outstanding = useOutstanding(customerId || null);
  const receivables = useReceivables(tab === 'receivables' || tab === 'collect');
  const history = usePaymentHistory({ limit: 50 }, tab === 'history');
  const receive = useReceivePayment();

  // Default the amount to whatever is outstanding when a customer is chosen.
  useEffect(() => {
    if (outstanding.data) setAmount(outstanding.data.total_outstanding);
  }, [outstanding.data]);

  const onReceive = async () => {
    if (!customerId || !amount || Number(amount) <= 0) return;
    setError(null);
    try {
      const result = await receive.mutateAsync({
        customerId,
        amount,
        method: method as PaymentMethod,
        reference: reference || undefined,
      });
      toast.success(
        `Received ${formatCurrency(amount)}`,
        Number(result.unallocated) > 0
          ? `${formatCurrency(result.allocated_total)} settled invoices · ${formatCurrency(result.unallocated)} held as advance.`
          : `Settled ${result.settled_invoice_ids.length} invoice(s).`,
      );
      setReference('');
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : 'The payment could not be recorded.';
      setError(message);
      toast.error('Payment not recorded', message);
    }
  };

  return (
    <>
      <StatGrid>
        <StatCard
          label="Total receivable"
          icon="collections"
          tone="warning"
          isLoading={receivables.isLoading}
          value={formatCurrency(receivables.data?.total_outstanding ?? '0')}
          hint="Across every customer with an open balance"
        />
        <StatCard
          label="Customers owing"
          icon="customers"
          isLoading={receivables.isLoading}
          value={receivables.data?.rows.length ?? 0}
          hint="With at least one unpaid invoice"
        />
        <StatCard
          label="Overdue past 30 days"
          icon="alert"
          tone={
            (receivables.data?.rows.filter((r) => r.days_overdue > 30).length ?? 0) > 0
              ? 'danger'
              : 'positive'
          }
          isLoading={receivables.isLoading}
          value={receivables.data?.rows.filter((r) => r.days_overdue > 30).length ?? 0}
          hint="Worth a phone call today"
        />
      </StatGrid>

      <Tabs<Tab>
        label="Collections sections"
        active={tab}
        onChange={setTab}
        items={[
          { id: 'collect', label: 'Receive payment', icon: 'collections' },
          { id: 'receivables', label: 'Who owes what', icon: 'customers' },
          { id: 'history', label: 'Payment history', icon: 'invoices' },
        ]}
      />

      {tab === 'collect' ? (
        <div className={styles.layout}>
          <Card>
            <CardHeader
              title="Open invoices"
              description="Oldest first — that is the order a payment settles them in."
            />
            <CardBody>
              <Select
                label="Customer"
                value={customerId}
                onChange={(event) => {
                  setCustomerId(event.target.value);
                  setError(null);
                }}
              >
                <option value="">Select a customer…</option>
                {(customers.data ?? []).map((customer) => (
                  <option key={customer.id} value={customer.id}>
                    {customer.name} ({customer.code})
                  </option>
                ))}
              </Select>
            </CardBody>

            {customerId ? (
              <QueryState
                isLoading={outstanding.isLoading}
                error={outstanding.error}
                onRetry={outstanding.refetch}
                loadingHeight={180}
              >
                <DataTable<OutstandingInvoice>
                  rows={outstanding.data?.invoices ?? []}
                  rowKey={(row) => row.id}
                  emptyTitle="Nothing outstanding"
                  emptyDescription="This customer has settled every invoice."
                  columns={[
                    {
                      key: 'invoice',
                      header: 'Invoice',
                      render: (row) => (
                        <span className={styles.primaryCell}>
                          <span>{row.invoice_number}</span>
                          <span className={styles.muted}>
                            {formatDate(row.invoice_date)}
                          </span>
                        </span>
                      ),
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
                      secondary: true,
                      render: (row) => formatCurrency(row.grand_total),
                    },
                    {
                      key: 'paid',
                      header: 'Paid',
                      numeric: true,
                      secondary: true,
                      render: (row) => formatCurrency(row.paid_amount),
                    },
                    {
                      key: 'outstanding',
                      header: 'Outstanding',
                      numeric: true,
                      render: (row) => (
                        <strong className={styles.due}>
                          {formatCurrency(row.outstanding)}
                        </strong>
                      ),
                    },
                  ]}
                />
              </QueryState>
            ) : (
              <CardBody>
                <p className={styles.muted}>
                  Choose a customer to see their open invoices.
                </p>
              </CardBody>
            )}
          </Card>

          <Card>
            <CardHeader
              title="Receive payment"
              description="Allocated oldest-invoice-first; anything left over is held as an advance."
            />
            <CardBody>
              <div className={styles.form}>
                <div className={styles.totalOut}>
                  <span>Total outstanding</span>
                  <strong className="tabular-nums">
                    {formatCurrency(outstanding.data?.total_outstanding ?? '0')}
                  </strong>
                </div>

                <Input
                  label="Amount received (₹)"
                  type="number"
                  min="0"
                  step="0.01"
                  value={amount}
                  onChange={(event) => setAmount(event.target.value)}
                />

                <Select
                  label="Method"
                  value={method}
                  onChange={(event) => setMethod(event.target.value)}
                >
                  {METHODS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>

                <Input
                  label="Reference"
                  value={reference}
                  placeholder="Cheque no., UPI ref, NEFT id…"
                  onChange={(event) => setReference(event.target.value)}
                />

                <Button
                  size="lg"
                  icon="check"
                  onClick={onReceive}
                  isLoading={receive.isPending}
                  disabled={!customerId || !amount || Number(amount) <= 0}
                >
                  Record payment
                </Button>

                {error ? (
                  <p role="alert" className={styles.error}>
                    {error}
                  </p>
                ) : null}
              </div>
            </CardBody>
          </Card>
        </div>
      ) : null}

      {tab === 'receivables' ? (
        <Card>
          <CardHeader
            title="Who owes what"
            description="Largest balance first. Days shown are since the oldest unpaid invoice."
          />
          <QueryState
            isLoading={receivables.isLoading}
            error={receivables.error}
            onRetry={receivables.refetch}
            loadingHeight={260}
          >
            <DataTable<ReceivableRow>
              rows={receivables.data?.rows ?? []}
              rowKey={(row) => row.customer_id}
              onRowClick={(row) => {
                setCustomerId(row.customer_id);
                setTab('collect');
              }}
              emptyTitle="Nothing outstanding"
              emptyDescription="Every invoice across the business has been settled."
              columns={[
                {
                  key: 'customer',
                  header: 'Customer',
                  render: (row) => (
                    <span className={styles.primaryCell}>
                      <span>{row.customer_name}</span>
                      <span className={styles.muted}>
                        {row.customer_code}
                        {row.phone ? ` · ${row.phone}` : ''}
                      </span>
                    </span>
                  ),
                },
                {
                  key: 'invoices',
                  header: 'Open invoices',
                  numeric: true,
                  secondary: true,
                  render: (row) => row.open_invoices,
                },
                {
                  key: 'oldest',
                  header: 'Oldest',
                  secondary: true,
                  render: (row) => formatDate(row.oldest_invoice_date),
                },
                {
                  key: 'age',
                  header: 'Age',
                  render: (row) => (
                    <Badge
                      tone={
                        row.days_overdue > 30
                          ? 'danger'
                          : row.days_overdue > 7
                            ? 'warning'
                            : 'neutral'
                      }
                    >
                      {row.days_overdue} days
                    </Badge>
                  ),
                },
                {
                  key: 'outstanding',
                  header: 'Outstanding',
                  numeric: true,
                  render: (row) => (
                    <strong className={styles.due}>
                      {formatCurrency(row.outstanding)}
                    </strong>
                  ),
                },
              ]}
            />
          </QueryState>
        </Card>
      ) : null}

      {tab === 'history' ? (
        <Card>
          <CardHeader
            title="Payment history"
            description="Money received, newest first, with who recorded it."
          />
          <QueryState
            isLoading={history.isLoading}
            error={history.error}
            onRetry={history.refetch}
            loadingHeight={260}
          >
            <DataTable<PaymentRecord>
              rows={history.data?.items ?? []}
              rowKey={(row) => row.id}
              emptyTitle="No payments recorded yet"
              columns={[
                {
                  key: 'when',
                  header: 'When',
                  render: (row) => formatDateTime(row.received_at),
                },
                {
                  key: 'customer',
                  header: 'Customer',
                  render: (row) => row.customer_name ?? 'Walk-in',
                },
                {
                  key: 'method',
                  header: 'Method',
                  render: (row) => <Badge tone="info">{humanize(row.method)}</Badge>,
                },
                {
                  key: 'reference',
                  header: 'Reference',
                  secondary: true,
                  render: (row) => row.reference ?? '—',
                },
                {
                  key: 'by',
                  header: 'Received by',
                  secondary: true,
                  render: (row) => row.received_by ?? '—',
                },
                {
                  key: 'amount',
                  header: 'Amount',
                  numeric: true,
                  render: (row) => <strong>{formatCurrency(row.amount)}</strong>,
                },
              ]}
              footer={
                <tr>
                  <td colSpan={5}>Total shown</td>
                  <td className="tabular-nums" style={{ textAlign: 'right' }}>
                    {formatCurrency(history.data?.total_amount ?? '0')}
                  </td>
                </tr>
              }
            />
          </QueryState>
        </Card>
      ) : null}
    </>
  );
}
