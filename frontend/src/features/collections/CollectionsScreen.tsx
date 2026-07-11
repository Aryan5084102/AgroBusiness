'use client';

import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { useCustomers } from '@/features/customers/useCustomers';
import type { PaymentMethod } from '@/features/pos/api';
import { ApiError } from '@/lib/api/client';
import { formatCurrency } from '@/lib/formatting/currency';
import { useOutstanding, useReceivePayment } from './useCollections';
import styles from './CollectionsScreen.module.scss';

const METHODS: PaymentMethod[] = ['cash', 'upi', 'card'];

// Receive a customer payment; the server allocates it FIFO across open invoices.
export function CollectionsScreen() {
  const customers = useCustomers();
  const [customerId, setCustomerId] = useState('');
  const outstanding = useOutstanding(customerId || null);
  const receive = useReceivePayment();

  const [amount, setAmount] = useState('');
  const [method, setMethod] = useState<PaymentMethod>('cash');
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ allocated: string; advance: string } | null>(
    null,
  );

  // Default the amount to the full outstanding when a customer is picked.
  useEffect(() => {
    if (outstanding.data) setAmount(outstanding.data.total_outstanding);
  }, [outstanding.data]);

  const onReceive = async () => {
    if (!customerId || !amount || Number(amount) <= 0) return;
    setError(null);
    setResult(null);
    try {
      const res = await receive.mutateAsync({ customerId, amount, method });
      setResult({ allocated: res.allocated_total, advance: res.unallocated });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not record the payment.');
    }
  };

  const dealers = customers.data ?? [];

  return (
    <div className={styles.wrap}>
      <section className={styles.left}>
        <div className={styles.row}>
          <label htmlFor="cust">Customer</label>
          <select
            id="cust"
            value={customerId}
            onChange={(e) => {
              setCustomerId(e.target.value);
              setResult(null);
              setError(null);
            }}
          >
            <option value="">Select a customer…</option>
            {dealers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.code})
              </option>
            ))}
          </select>
        </div>

        {customerId ? (
          outstanding.isLoading ? (
            <p className={styles.muted}>Loading invoices…</p>
          ) : (outstanding.data?.invoices.length ?? 0) === 0 ? (
            <p className={styles.muted}>No outstanding invoices — fully settled.</p>
          ) : (
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Invoice</th>
                    <th>Date</th>
                    <th className={styles.num}>Total</th>
                    <th className={styles.num}>Paid</th>
                    <th className={styles.num}>Outstanding</th>
                  </tr>
                </thead>
                <tbody>
                  {outstanding.data?.invoices.map((i) => (
                    <tr key={i.id}>
                      <td className={styles.mono}>{i.invoice_number}</td>
                      <td>{i.invoice_date}</td>
                      <td className={`${styles.num} tabular-nums`}>
                        {formatCurrency(i.grand_total)}
                      </td>
                      <td className={`${styles.num} tabular-nums`}>
                        {formatCurrency(i.paid_amount)}
                      </td>
                      <td className={`${styles.num} tabular-nums`}>
                        {formatCurrency(i.outstanding)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : (
          <p className={styles.muted}>Select a customer to view outstanding invoices.</p>
        )}
      </section>

      <aside className={styles.panel}>
        <h3 className={styles.panelTitle}>Receive payment</h3>
        <div className={styles.totalOut}>
          <span>Total outstanding</span>
          <strong className="tabular-nums">
            {formatCurrency(outstanding.data?.total_outstanding ?? '0')}
          </strong>
        </div>
        <label className={styles.field}>
          <span>Amount received (₹)</span>
          <input
            type="number"
            min={0}
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
        </label>
        <div className={styles.methods} role="group" aria-label="Payment method">
          {METHODS.map((m) => (
            <button
              key={m}
              type="button"
              className={`${styles.method} ${method === m ? styles.methodActive : ''}`}
              aria-pressed={method === m}
              onClick={() => setMethod(m)}
            >
              {m.toUpperCase()}
            </button>
          ))}
        </div>
        <Button
          size="lg"
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
        {result ? (
          <p role="status" className={styles.success}>
            Allocated {formatCurrency(result.allocated)}
            {Number(result.advance) > 0
              ? ` · ${formatCurrency(result.advance)} kept as advance`
              : ''}
            .
          </p>
        ) : null}
      </aside>
    </div>
  );
}
