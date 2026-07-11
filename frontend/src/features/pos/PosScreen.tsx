'use client';

import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { ApiError } from '@/lib/api/client';
import { formatCurrency } from '@/lib/formatting/currency';
import type { PaymentMethod } from './api';
import { ProductPicker } from './ProductPicker';
import { useCart } from './useCart';
import { useFinalizeSale, useQuote, useWarehouses } from './usePos';
import styles from './PosScreen.module.scss';

const METHODS: PaymentMethod[] = ['cash', 'upi', 'card'];

// Retail POS counter: pick warehouse, search → cart, live authoritative quote,
// pay in full (walk-in), finalize with an idempotency key.
export function PosScreen() {
  const warehouses = useWarehouses();
  const [warehouseId, setWarehouseId] = useState<string | null>(null);
  const cart = useCart();
  const quote = useQuote(warehouseId, cart.lines);
  const finalize = useFinalizeSale();

  const [method, setMethod] = useState<PaymentMethod>('cash');
  const [idempotencyKey, setIdempotencyKey] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<{ number: string; total: string } | null>(null);

  // Default the warehouse to the first available; mint an idempotency key per cart.
  useEffect(() => {
    if (!warehouseId && warehouses.data && warehouses.data.length > 0) {
      setWarehouseId(warehouses.data[0]!.id);
    }
  }, [warehouseId, warehouses.data]);
  useEffect(() => {
    if (!idempotencyKey) setIdempotencyKey(crypto.randomUUID());
  }, [idempotencyKey]);

  const grandTotal = quote.data?.grand_total ?? '0.00';
  const byProduct = useMemo(
    () => new Map((quote.data?.lines ?? []).map((l) => [l.product_id, l])),
    [quote.data],
  );

  const onFinalize = async () => {
    if (!warehouseId || cart.items.length === 0) return;
    setError(null);
    try {
      const result = await finalize.mutateAsync({
        warehouseId,
        lines: cart.lines,
        method,
        amount: grandTotal, // walk-in pays the authoritative total in full
        idempotencyKey,
      });
      setReceipt({ number: result.invoice_number, total: result.grand_total });
      cart.clear();
      setIdempotencyKey(crypto.randomUUID());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not complete the sale.');
    }
  };

  return (
    <div className={styles.pos}>
      <section className={styles.left}>
        <div className={styles.warehouseRow}>
          <label htmlFor="wh">Selling from</label>
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
        <ProductPicker onAdd={cart.add} />
      </section>

      <section className={styles.cart}>
        <h3 className={styles.cartTitle}>Cart</h3>
        {cart.items.length === 0 ? (
          <p className={styles.empty}>Search and click a product to add it.</p>
        ) : (
          <ul role="list" className={styles.lines}>
            {cart.items.map((item) => {
              const q = byProduct.get(item.productId);
              const shortStock = q && Number(q.available_stock) < item.quantity;
              return (
                <li key={item.productId} className={styles.line}>
                  <div className={styles.lineMain}>
                    <span className={styles.lineName}>{item.name}</span>
                    <button
                      type="button"
                      className={styles.remove}
                      aria-label={`Remove ${item.name}`}
                      onClick={() => cart.remove(item.productId)}
                    >
                      ✕
                    </button>
                  </div>
                  <div className={styles.lineControls}>
                    <input
                      type="number"
                      min={1}
                      value={item.quantity}
                      aria-label={`Quantity for ${item.name}`}
                      onChange={(e) =>
                        cart.setQuantity(item.productId, Number(e.target.value))
                      }
                    />
                    <span className={`${styles.lineTotal} tabular-nums`}>
                      {q ? formatCurrency(q.line_total) : '…'}
                    </span>
                  </div>
                  {q ? (
                    <span className={shortStock ? styles.stockShort : styles.stockOk}>
                      {shortStock ? '⚠ ' : ''}
                      {q.available_stock} in stock
                    </span>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}

        <dl className={styles.totals}>
          <div>
            <dt>Subtotal</dt>
            <dd className="tabular-nums">
              {formatCurrency(quote.data?.subtotal ?? '0')}
            </dd>
          </div>
          <div>
            <dt>Tax</dt>
            <dd className="tabular-nums">
              {formatCurrency(quote.data?.tax_total ?? '0')}
            </dd>
          </div>
          <div className={styles.grand}>
            <dt>Total</dt>
            <dd className="tabular-nums">{formatCurrency(grandTotal)}</dd>
          </div>
        </dl>

        <div className={styles.payRow} role="group" aria-label="Payment method">
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
          onClick={onFinalize}
          isLoading={finalize.isPending}
          disabled={cart.items.length === 0 || !quote.data}
        >
          Finalize — {formatCurrency(grandTotal)}
        </Button>

        {error ? (
          <p role="alert" className={styles.error}>
            {error}
          </p>
        ) : null}
        {receipt ? (
          <p role="status" className={styles.receipt}>
            Invoice {receipt.number} finalized · {formatCurrency(receipt.total)}
          </p>
        ) : null}
      </section>
    </div>
  );
}
