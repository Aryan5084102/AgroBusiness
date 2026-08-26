'use client';

import Link from 'next/link';
import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { Icon } from '@/components/ui/Icon';
import { Input, Select } from '@/components/ui/Field';
import { useToast } from '@/components/ui/Toast';
import { fetchInvoice, type InvoiceDetail } from '@/features/invoices/api';
import { downloadInvoicePdf } from '@/features/invoices/invoicePdf';
import { useOrgProfile, useWarehouses } from '@/features/settings/useSettings';
import { ApiError } from '@/lib/api/client';
import { formatCurrency } from '@/lib/formatting/currency';
import type { PaymentMethod } from './api';
import { CustomerFields } from './CustomerCard';
import { ProductPicker } from './ProductPicker';
import { useCart } from './useCart';
import { useFinalizeSale, useQuote } from './usePos';
import {
  EMPTY_DRAFT,
  isCompletePhone,
  useCustomerByPhone,
  useResolveCustomer,
  type CustomerDraft,
} from './useCounterCustomer';
import styles from './PosScreen.module.scss';

const METHODS: { value: PaymentMethod; label: string }[] = [
  { value: 'cash', label: 'Cash' },
  { value: 'upi', label: 'UPI' },
  { value: 'card', label: 'Card' },
];

type DraftErrors = Partial<Record<keyof CustomerDraft, string>>;

function validate(draft: CustomerDraft): DraftErrors {
  const errors: DraftErrors = {};
  if (!draft.name.trim()) errors.name = 'The bill needs a name to print.';
  if (!draft.phone.trim()) errors.phone = 'A mobile number is required.';
  else if (!isCompletePhone(draft.phone)) errors.phone = 'Enter all 10 digits.';
  return errors;
}

/**
 * The counter. Customer → search → cart → live authoritative quote → payment →
 * the bill lands in the counter's downloads.
 *
 * Prices and totals always come from the server, so what the customer is
 * charged is exactly what the invoice records.
 */
export function PosScreen() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const warehouses = useWarehouses();
  const org = useOrgProfile();
  const cart = useCart();
  const finalize = useFinalizeSale();
  const resolveCustomer = useResolveCustomer();

  const [warehouseId, setWarehouseId] = useState<string>('');
  // Every bill names its buyer, so the counter takes the details before the
  // goods. A mobile already on file is recognised rather than duplicated.
  const [draft, setDraft] = useState<CustomerDraft>(EMPTY_DRAFT);
  const [showErrors, setShowErrors] = useState(false);
  const [onCredit, setOnCredit] = useState(false);
  const [paidNow, setPaidNow] = useState<string>('0');
  const [method, setMethod] = useState<PaymentMethod>('cash');
  const [idempotencyKey, setIdempotencyKey] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Keeps the finished invoice so the counter can re-download or print the bill
  // for the sale it just rang up, without hunting for it in the invoice list.
  const [receipt, setReceipt] = useState<InvoiceDetail | null>(null);

  const quote = useQuote(warehouseId || null, cart.lines);
  const lookup = useCustomerByPhone(draft.phone);
  const known = lookup.data ?? null;

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

  // A recognised number fills in what the shop already knows, but never
  // overwrites something the counter has typed for this sale.
  useEffect(() => {
    if (!known) return;
    setDraft((prev) => ({
      name: prev.name.trim() ? prev.name : known.name,
      phone: prev.phone,
      address: prev.address.trim() ? prev.address : (known.address ?? ''),
    }));
  }, [known]);

  const grandTotal = quote.data?.grand_total ?? '0.00';
  const byProduct = useMemo(
    () => new Map((quote.data?.lines ?? []).map((line) => [line.product_id, line])),
    [quote.data],
  );
  // A walk-in settles the whole bill; on khata, whatever is handed over now
  // (possibly nothing) is a part payment against it.
  const amountTaken = onCredit ? paidNow || '0' : grandTotal;
  const draftErrors = validate(draft);
  const shortLines = cart.items.filter((item) => {
    const line = byProduct.get(item.productId);
    return line !== undefined && Number(line.available_stock) < item.quantity;
  });

  // Payment is blocked until the server has priced the cart, so the screen has
  // to say which of those things it is still waiting on. A disabled button with
  // no reason beside it reads as a broken till.
  const pricing = cart.items.length > 0 && !quote.data && !quote.isError;
  const blocker = quote.isError
    ? 'Prices could not be fetched, so the bill cannot be totalled yet.'
    : pricing
      ? 'Getting prices from the server…'
      : shortLines.length > 0
        ? 'Reduce the highlighted lines — there is not enough stock to sell them.'
        : cart.items.length === 0
          ? 'Add an item to start the bill.'
          : null;
  const quoteMessage =
    quote.error instanceof ApiError
      ? quote.error.status === 401
        ? 'Your session has expired. Sign in again to price this bill.'
        : quote.error.message
      : 'The server could not be reached to price this bill.';

  const handOverBill = (invoice: InvoiceDetail): boolean =>
    downloadInvoicePdf(invoice, org.data ?? null);

  const onFinalize = async () => {
    if (!warehouseId || cart.items.length === 0) return;
    if (Object.keys(draftErrors).length > 0) {
      setShowErrors(true);
      setError('Fill in the customer name and mobile number before taking payment.');
      return;
    }
    if (Number(amountTaken) > Number(grandTotal)) {
      setError('Amount taken cannot be more than the bill.');
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const customer = await resolveCustomer(draft, known);
      const result = await finalize.mutateAsync({
        warehouseId,
        customerId: customer.id,
        lines: cart.lines,
        method,
        amount: amountTaken, // server-quoted total, never a client-side sum
        idempotencyKey,
      });

      // Re-read the finalized invoice: the bill has to print what the server
      // stored (its numbering, its tax split), not what the cart guessed.
      const invoice = await queryClient.fetchQuery({
        queryKey: ['invoice', result.invoice_id],
        queryFn: () => fetchInvoice(result.invoice_id),
      });
      setReceipt(invoice);
      const downloaded = handOverBill(invoice);

      toast.success(
        `Invoice ${result.invoice_number}`,
        downloaded
          ? `${formatCurrency(result.grand_total)} taken. The bill has been downloaded.`
          : `${formatCurrency(result.grand_total)} taken by ${method.toUpperCase()}.`,
      );
      if (!downloaded) {
        toast.error(
          'Bill not downloaded',
          'Use “Download bill” below to save it, or open the printable copy.',
        );
      }

      cart.clear();
      setDraft(EMPTY_DRAFT);
      setShowErrors(false);
      setOnCredit(false);
      setPaidNow('0');
      setIdempotencyKey(crypto.randomUUID());
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : 'The sale could not be completed.';
      setError(message);
      toast.error('Sale not completed', message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={styles.pos}>
      <div className={styles.left}>
        <Card>
          <CardHeader
            title="Customer"
            description="These details print on the bill. A number already on file is recognised."
          />
          <CardBody>
            <CustomerFields
              draft={draft}
              known={known}
              isLooking={lookup.isFetching}
              errors={showErrors ? draftErrors : {}}
              onChange={(field, value) => {
                setDraft((prev) => ({ ...prev, [field]: value }));
                // The last sale's bill must not linger beside a new customer's
                // details — it reads as if this sale were already invoiced.
                setReceipt(null);
              }}
            />

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
              <label className={styles.creditToggle}>
                <input
                  type="checkbox"
                  checked={onCredit}
                  onChange={(event) => {
                    setOnCredit(event.target.checked);
                    if (!event.target.checked) setPaidNow('0');
                  }}
                />
                <span>
                  Sale on credit (khata)
                  <span className={styles.creditToggleHint}>
                    Paid in full unless you tick this.
                  </span>
                </span>
              </label>
              {onCredit ? (
                <Input
                  label="Taken now (₹)"
                  type="number"
                  min="0"
                  step="0.01"
                  hint="Leave 0 to put the whole bill on khata."
                  value={paidNow}
                  onChange={(event) => setPaidNow(event.target.value)}
                />
              ) : null}
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Add items"
            description="Type a name, SKU or barcode, then click to add it to the bill."
          />
          <CardBody>
            <ProductPicker
              onAdd={(productId, name) => {
                setReceipt(null);
                cart.add(productId, name);
              }}
            />
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
            {draft.name.trim() ? (
              <p className={styles.billFor}>
                For <strong>{draft.name.trim()}</strong>
                {draft.phone.trim() ? ` · ${draft.phone.trim()}` : ''}
              </p>
            ) : null}

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

            {quote.isError ? (
              <div role="alert" className={styles.quoteError}>
                <span className={styles.quoteErrorText}>
                  <Icon name="alert" size={15} />
                  {quoteMessage}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  icon="refresh"
                  onClick={() => quote.refetch()}
                  isLoading={quote.isFetching}
                >
                  Try again
                </Button>
              </div>
            ) : null}

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

            {onCredit ? (
              <p className={styles.creditNote}>
                {known && Number(known.credit_limit) > 0 ? (
                  <>
                    {known.name} has {formatCurrency(known.available_credit)} credit
                    available.{' '}
                  </>
                ) : null}
                {formatCurrency(Math.max(Number(grandTotal) - Number(amountTaken), 0))}{' '}
                goes on their khata.
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
              isLoading={busy || finalize.isPending}
              disabled={cart.items.length === 0 || !quote.data || shortLines.length > 0}
            >
              {onCredit && Number(amountTaken) === 0
                ? `Put ${formatCurrency(grandTotal)} on khata`
                : `Take payment — ${formatCurrency(amountTaken)}`}
            </Button>
            <p
              role="status"
              className={`${styles.payHint} ${blocker ? styles.payHintBlocked : ''}`}
            >
              {blocker ??
                'The bill downloads as a PDF as soon as the payment goes through.'}
            </p>
            {error ? (
              <p role="alert" className={styles.error}>
                {error}
              </p>
            ) : null}
            {receipt ? (
              <div role="status" className={styles.receipt}>
                <p className={styles.receiptLine}>
                  <Icon name="check" size={15} /> Invoice {receipt.invoice_number} ·{' '}
                  {formatCurrency(receipt.grand_total)}
                </p>
                <span className={styles.receiptActions}>
                  <button
                    type="button"
                    className={styles.receiptAction}
                    onClick={() => handOverBill(receipt)}
                  >
                    <Icon name="download" size={14} /> Download bill
                  </button>
                  <Link
                    href={`/invoices/${receipt.id}/bill`}
                    className={styles.receiptAction}
                  >
                    <Icon name="print" size={14} /> Print bill
                  </Link>
                </span>
              </div>
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
