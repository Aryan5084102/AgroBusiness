'use client';

import { useEffect, useMemo, useState } from 'react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { Icon } from '@/components/ui/Icon';
import { Select } from '@/components/ui/Field';
import { useToast } from '@/components/ui/Toast';
import { useCustomers } from '@/features/customers/useCustomers';
import { useWarehouses } from '@/features/settings/useSettings';
import { ApiError } from '@/lib/api/client';
import { formatCurrency } from '@/lib/formatting/currency';
import type { PaymentMethod } from './api';
import { ProductPicker } from './ProductPicker';
import { useCart } from './useCart';
import { useFinalizeSale, useQuote } from './usePos';
import styles from './PosScreen.module.scss';

const METHODS: { value: PaymentMethod; label: string }[] = [
  { value: 'cash', label: 'Cash' },
  { value: 'upi', label: 'UPI' },
  { value: 'card', label: 'Card' },
];

/**
 * The counter. Search → cart → live authoritative quote → payment → invoice.
 * Prices and totals always come from the server, so what the customer is
 * charged is exactly what the invoice records.
 */
export function PosScreen() {
  const toast = useToast();
  const warehouses = useWarehouses();
  const customers = useCustomers();
  const cart = useCart();
  const finalize = useFinalizeSale();

  const [warehouseId, setWarehouseId] = useState<string>('');
  const [customerId, setCustomerId] = useState<string>('');
  const [method, setMethod] = useState<PaymentMethod>('cash');
  const [idempotencyKey, setIdempotencyKey] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<{ number: string; total: string } | null>(null);

  const quote = useQuote(warehouseId || null, cart.lines);

  // Sell from the shop counter by default, not the bulk godown; mint one
  // idempotency key per cart so a double-click can never bill twice.
  useEffect(() => {
    if (!warehouseId && warehouses.data && warehouses.data.length > 0) {
      const shop = warehouses.data.find((w) => w.type === 'shop');
      setWarehouseId((shop ?? warehouses.data[0]!).id);
    }
  }, [warehouseId, warehouses.data]);
  useEffect(() => {
    if (!idempotencyKey) setIdempotencyKey(crypto.randomUUID());
  }, [idempotencyKey]);

  const grandTotal = quote.data?.grand_total ?? '0.00';
  const byProduct = useMemo(
    () => new Map((quote.data?.lines ?? []).map((line) => [line.product_id, line])),
    [quote.data],
  );
  const selectedCustomer = customers.data?.find((c) => c.id === customerId) ?? null;
  const shortLines = cart.items.filter((item) => {
    const line = byProduct.get(item.productId);
    return line !== undefined && Number(line.available_stock) < item.quantity;
  });

  const onFinalize = async () => {
    if (!warehouseId || cart.items.length === 0) return;
    setError(null);
    try {
      const result = await finalize.mutateAsync({
        warehouseId,
        customerId: customerId || null,
        lines: cart.lines,
        method,
        amount: grandTotal, // the authoritative total, never a client-side sum
        idempotencyKey,
      });
      setReceipt({ number: result.invoice_number, total: result.grand_total });
      toast.success(
        `Invoice ${result.invoice_number}`,
        `${formatCurrency(result.grand_total)} taken by ${method.toUpperCase()}.`,
      );
      cart.clear();
      setIdempotencyKey(crypto.randomUUID());
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : 'The sale could not be completed.';
      setError(message);
      toast.error('Sale not completed', message);
    }
  };

  return (
    <div className={styles.pos}>
      <div className={styles.left}>
        <Card>
          <CardBody>
            <div className={styles.contextRow}>
              <Select
                label="Selling from"
                value={warehouseId}
                onChange={(event) => setWarehouseId(event.target.value)}
              >
                {(warehouses.data ?? []).map((warehouse) => (
                  <option key={warehouse.id} value={warehouse.id}>
                    {warehouse.name} ({warehouse.code})
                  </option>
                ))}
              </Select>
              <Select
                label="Customer"
                value={customerId}
                hint="Leave blank for a walk-in — walk-ins must pay in full."
                onChange={(event) => setCustomerId(event.target.value)}
              >
                <option value="">Walk-in customer</option>
                {(customers.data ?? []).map((customer) => (
                  <option key={customer.id} value={customer.id}>
                    {customer.name}
                  </option>
                ))}
              </Select>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Add items"
            description="Type a name, SKU or barcode, then click to add it to the bill."
          />
          <CardBody>
            <ProductPicker onAdd={cart.add} />
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader
          title="Current bill"
          description={
            cart.items.length > 0
              ? `${cart.items.length} line${cart.items.length === 1 ? '' : 's'}`
              : undefined
          }
          actions={
            cart.items.length > 0 ? (
              <Button variant="ghost" size="sm" icon="trash" onClick={cart.clear}>
                Clear
              </Button>
            ) : null
          }
        />
        <CardBody>
          <div className={styles.bill}>
            {cart.items.length === 0 ? (
              <EmptyState
                icon="pos"
                title="No items yet"
                description="Search the catalogue and pick a product to start the bill."
              />
            ) : (
              <ul role="list" className={styles.lines}>
                {cart.items.map((item) => {
                  const line = byProduct.get(item.productId);
                  const short =
                    line !== undefined && Number(line.available_stock) < item.quantity;
                  return (
                    <li key={item.productId} className={styles.line}>
                      <div className={styles.lineTop}>
                        <span className={styles.lineName}>{item.name}</span>
                        <button
                          type="button"
                          className={styles.remove}
                          aria-label={`Remove ${item.name}`}
                          onClick={() => cart.remove(item.productId)}
                        >
                          <Icon name="close" size={15} />
                        </button>
                      </div>
                      <div className={styles.lineControls}>
                        <div className={styles.stepper}>
                          <button
                            type="button"
                            aria-label={`Reduce ${item.name}`}
                            onClick={() =>
                              cart.setQuantity(item.productId, item.quantity - 1)
                            }
                          >
                            −
                          </button>
                          <input
                            type="number"
                            min={1}
                            value={item.quantity}
                            aria-label={`Quantity for ${item.name}`}
                            onChange={(event) =>
                              cart.setQuantity(item.productId, Number(event.target.value))
                            }
                          />
                          <button
                            type="button"
                            aria-label={`Increase ${item.name}`}
                            onClick={() =>
                              cart.setQuantity(item.productId, item.quantity + 1)
                            }
                          >
                            +
                          </button>
                        </div>
                        <span className={`${styles.lineTotal} tabular-nums`}>
                          {line ? formatCurrency(line.line_total) : '…'}
                        </span>
                      </div>
                      {line ? (
                        <span className={styles.lineMeta}>
                          {short ? (
                            <Badge tone="danger" dot>
                              Only {line.available_stock} in stock
                            </Badge>
                          ) : (
                            <span className={styles.muted}>
                              {formatCurrency(line.unit_price)} each ·{' '}
                              {line.available_stock} available
                            </span>
                          )}
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
                <dt>GST</dt>
                <dd className="tabular-nums">
                  {formatCurrency(quote.data?.tax_total ?? '0')}
                </dd>
              </div>
              <div className={styles.grand}>
                <dt>To pay</dt>
                <dd className="tabular-nums">{formatCurrency(grandTotal)}</dd>
              </div>
            </dl>

            {selectedCustomer && Number(selectedCustomer.credit_limit) > 0 ? (
              <p className={styles.creditNote}>
                {selectedCustomer.name} has{' '}
                {formatCurrency(selectedCustomer.available_credit)} credit available.
              </p>
            ) : null}

            <div className={styles.methods} role="group" aria-label="Payment method">
              {METHODS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className={`${styles.method} ${
                    method === option.value ? styles.methodActive : ''
                  }`}
                  aria-pressed={method === option.value}
                  onClick={() => setMethod(option.value)}
                >
                  {option.label}
                </button>
              ))}
            </div>

            <Button
              size="lg"
              icon="check"
              onClick={onFinalize}
              isLoading={finalize.isPending}
              disabled={cart.items.length === 0 || !quote.data || shortLines.length > 0}
            >
              Take payment — {formatCurrency(grandTotal)}
            </Button>

            {shortLines.length > 0 ? (
              <p role="alert" className={styles.error}>
                Reduce the highlighted lines — there is not enough stock to sell them.
              </p>
            ) : null}
            {error ? (
              <p role="alert" className={styles.error}>
                {error}
              </p>
            ) : null}
            {receipt ? (
              <p role="status" className={styles.receipt}>
                <Icon name="check" size={15} /> Invoice {receipt.number} ·{' '}
                {formatCurrency(receipt.total)}
              </p>
            ) : null}
            {(quote.data?.warnings.length ?? 0) > 0 ? (
              <ul className={styles.warnings}>
                {quote.data?.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            ) : null}
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
