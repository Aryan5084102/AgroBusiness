'use client';

import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { useCustomers } from '@/features/customers/useCustomers';
import { ProductPicker } from '@/features/pos/ProductPicker';
import { useCart } from '@/features/pos/useCart';
import { useWarehouses } from '@/features/pos/usePos';
import { ApiError } from '@/lib/api/client';
import { formatCurrency } from '@/lib/formatting/currency';
import type { OrderResult } from './api';
import { useCreateOrder, useDispatchOrder } from './useWholesale';
import styles from './WholesaleScreen.module.scss';

// Wholesale order builder: pick dealer (with credit), build cart, confirm order
// (reserves stock, credit-checked), then dispatch → invoice.
export function WholesaleScreen() {
  const warehouses = useWarehouses();
  const customers = useCustomers();
  const cart = useCart();
  const createOrder = useCreateOrder();
  const dispatchOrder = useDispatchOrder();

  const [warehouseId, setWarehouseId] = useState<string | null>(null);
  const [customerId, setCustomerId] = useState<string>('');
  const [creditBlocked, setCreditBlocked] = useState(false);
  const [override, setOverride] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [order, setOrder] = useState<OrderResult | null>(null);
  const [invoiceNumber, setInvoiceNumber] = useState<string | null>(null);

  useEffect(() => {
    if (!warehouseId && warehouses.data && warehouses.data.length > 0) {
      setWarehouseId(warehouses.data[0]!.id);
    }
  }, [warehouseId, warehouses.data]);

  const selectedCustomer = useMemo(
    () => customers.data?.find((c) => c.id === customerId) ?? null,
    [customers.data, customerId],
  );

  const resetOrder = () => {
    setOrder(null);
    setInvoiceNumber(null);
    setCreditBlocked(false);
    setOverride(false);
  };

  const onConfirm = async () => {
    if (!warehouseId || !customerId || cart.items.length === 0) return;
    setError(null);
    try {
      const result = await createOrder.mutateAsync({
        warehouseId,
        customerId,
        lines: cart.lines,
        creditOverrideApproved: override,
      });
      setOrder(result);
      setCreditBlocked(false);
      cart.clear();
    } catch (err) {
      if (err instanceof ApiError && err.code === 'credit_limit_exceeded') {
        setCreditBlocked(true);
        setError(err.message);
      } else {
        setError(err instanceof ApiError ? err.message : 'Could not create the order.');
      }
    }
  };

  const onDispatch = async () => {
    if (!order) return;
    setError(null);
    try {
      const result = await dispatchOrder.mutateAsync(order.sales_order_id);
      setInvoiceNumber(result.invoice_number);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not dispatch the order.');
    }
  };

  return (
    <div className={styles.wrap}>
      <section className={styles.controls}>
        <div className={styles.row}>
          <label htmlFor="wh">Warehouse</label>
          <select
            id="wh"
            value={warehouseId ?? ''}
            onChange={(e) => setWarehouseId(e.target.value)}
          >
            {(warehouses.data ?? []).map((w) => (
              <option key={w.id} value={w.id}>
                {w.name} ({w.code})
              </option>
            ))}
          </select>
        </div>
        <div className={styles.row}>
          <label htmlFor="cust">Dealer</label>
          <select
            id="cust"
            value={customerId}
            onChange={(e) => {
              setCustomerId(e.target.value);
              resetOrder();
            }}
          >
            <option value="">Select a dealer…</option>
            {(customers.data ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.code})
              </option>
            ))}
          </select>
        </div>

        {selectedCustomer ? (
          <dl className={styles.credit}>
            <div>
              <dt>Credit limit</dt>
              <dd className="tabular-nums">
                {formatCurrency(selectedCustomer.credit_limit)}
              </dd>
            </div>
            <div>
              <dt>Outstanding</dt>
              <dd className="tabular-nums">
                {formatCurrency(selectedCustomer.outstanding)}
              </dd>
            </div>
            <div className={styles.available}>
              <dt>Available credit</dt>
              <dd className="tabular-nums">
                {formatCurrency(selectedCustomer.available_credit)}
              </dd>
            </div>
          </dl>
        ) : null}

        <ProductPicker onAdd={cart.add} />
      </section>

      <section className={styles.cart}>
        <h3 className={styles.cartTitle}>Order lines</h3>
        {cart.items.length === 0 && !order ? (
          <p className={styles.muted}>Add products to build the order.</p>
        ) : (
          <ul role="list" className={styles.lines}>
            {cart.items.map((item) => (
              <li key={item.productId} className={styles.line}>
                <span className={styles.lineName}>{item.name}</span>
                <input
                  type="number"
                  min={1}
                  value={item.quantity}
                  aria-label={`Quantity for ${item.name}`}
                  onChange={(e) =>
                    cart.setQuantity(item.productId, Number(e.target.value))
                  }
                />
                <button
                  type="button"
                  className={styles.remove}
                  aria-label={`Remove ${item.name}`}
                  onClick={() => cart.remove(item.productId)}
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}

        {!order ? (
          <>
            {creditBlocked ? (
              <label className={styles.override}>
                <input
                  type="checkbox"
                  checked={override}
                  onChange={(e) => setOverride(e.target.checked)}
                />
                Approve credit-limit override
              </label>
            ) : null}
            <Button
              size="lg"
              onClick={onConfirm}
              isLoading={createOrder.isPending}
              disabled={!customerId || cart.items.length === 0}
            >
              Confirm order
            </Button>
          </>
        ) : (
          <div className={styles.orderResult}>
            <p className={styles.orderLine}>
              <strong>{order.order_number}</strong> · {order.status} ·{' '}
              <span className="tabular-nums">{formatCurrency(order.grand_total)}</span>
            </p>
            {invoiceNumber ? (
              <p role="status" className={styles.invoice}>
                Dispatched — invoice {invoiceNumber} (on credit)
              </p>
            ) : (
              <Button size="lg" onClick={onDispatch} isLoading={dispatchOrder.isPending}>
                Dispatch &amp; invoice
              </Button>
            )}
            <button type="button" className={styles.newOrder} onClick={resetOrder}>
              Start a new order
            </button>
          </div>
        )}

        {error ? (
          <p role="alert" className={styles.error}>
            {error}
          </p>
        ) : null}
      </section>
    </div>
  );
}
