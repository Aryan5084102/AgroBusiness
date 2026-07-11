'use client';

import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { ProductPicker } from '@/features/pos/ProductPicker';
import { useWarehouses } from '@/features/pos/usePos';
import { ApiError } from '@/lib/api/client';
import { formatCurrency } from '@/lib/formatting/currency';
import { useCreateGoodsReceipt, useSupplierOptions } from './useGoodsReceipt';
import styles from './GoodsReceiptScreen.module.scss';

interface ReceiptRow {
  productId: string;
  name: string;
  quantity: string;
  rate: string;
  batch: string;
  expiry: string;
}

// Receive stock from a supplier into a warehouse; posts to the stock ledger and
// returns the computed landed unit cost per product.
export function GoodsReceiptScreen() {
  const warehouses = useWarehouses();
  const suppliers = useSupplierOptions();
  const create = useCreateGoodsReceipt();

  const [warehouseId, setWarehouseId] = useState<string | null>(null);
  const [supplierId, setSupplierId] = useState('');
  const [freight, setFreight] = useState('0');
  const [rows, setRows] = useState<ReceiptRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{
    grn: string;
    costs: { product_id: string; landed_unit_cost: string }[];
    names: Record<string, string>;
  } | null>(null);

  useEffect(() => {
    if (!warehouseId && warehouses.data && warehouses.data.length > 0) {
      setWarehouseId(warehouses.data[0]!.id);
    }
  }, [warehouseId, warehouses.data]);

  const addProduct = (productId: string, name: string) => {
    setResult(null);
    setRows((prev) =>
      prev.some((r) => r.productId === productId)
        ? prev
        : [...prev, { productId, name, quantity: '1', rate: '0', batch: '', expiry: '' }],
    );
  };

  const patch = (productId: string, field: keyof ReceiptRow, value: string) => {
    setRows((prev) =>
      prev.map((r) => (r.productId === productId ? { ...r, [field]: value } : r)),
    );
  };

  const removeRow = (productId: string) =>
    setRows((prev) => prev.filter((r) => r.productId !== productId));

  const canSubmit =
    Boolean(warehouseId) &&
    Boolean(supplierId) &&
    rows.length > 0 &&
    rows.every((r) => Number(r.quantity) > 0);

  const onSubmit = async () => {
    if (!warehouseId || !supplierId || rows.length === 0) return;
    setError(null);
    try {
      const res = await create.mutateAsync({
        warehouseId,
        supplierId,
        freight,
        lines: rows.map((r) => ({
          product_id: r.productId,
          received_base_quantity: r.quantity,
          unit_rate: r.rate || '0',
          batch_number: r.batch || undefined,
          expiry_date: r.expiry || undefined,
        })),
      });
      const names = Object.fromEntries(rows.map((r) => [r.productId, r.name]));
      setResult({ grn: res.grn_number, costs: res.landed_unit_costs, names });
      setRows([]);
      setFreight('0');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save the receipt.');
    }
  };

  return (
    <div className={styles.wrap}>
      <section className={styles.left}>
        <div className={styles.controls}>
          <div className={styles.row}>
            <label htmlFor="wh">Receive into</label>
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
            <label htmlFor="sup">Supplier</label>
            <select
              id="sup"
              value={supplierId}
              onChange={(e) => setSupplierId(e.target.value)}
            >
              <option value="">Select a supplier…</option>
              {(suppliers.data ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.code})
                </option>
              ))}
            </select>
          </div>
        </div>
        <ProductPicker onAdd={addProduct} />
      </section>

      <section className={styles.panel}>
        <h3 className={styles.panelTitle}>Receipt lines</h3>
        {rows.length === 0 ? (
          <p className={styles.muted}>Search and add products to receive.</p>
        ) : (
          <ul role="list" className={styles.rows}>
            {rows.map((r) => (
              <li key={r.productId} className={styles.rowItem}>
                <div className={styles.rowHead}>
                  <span className={styles.rowName}>{r.name}</span>
                  <button
                    type="button"
                    className={styles.remove}
                    aria-label={`Remove ${r.name}`}
                    onClick={() => removeRow(r.productId)}
                  >
                    ✕
                  </button>
                </div>
                <div className={styles.fields}>
                  <label>
                    Qty
                    <input
                      type="number"
                      min={1}
                      value={r.quantity}
                      onChange={(e) => patch(r.productId, 'quantity', e.target.value)}
                    />
                  </label>
                  <label>
                    Rate ₹
                    <input
                      type="number"
                      min={0}
                      step="0.01"
                      value={r.rate}
                      onChange={(e) => patch(r.productId, 'rate', e.target.value)}
                    />
                  </label>
                  <label>
                    Batch
                    <input
                      value={r.batch}
                      onChange={(e) => patch(r.productId, 'batch', e.target.value)}
                    />
                  </label>
                  <label>
                    Expiry
                    <input
                      type="date"
                      value={r.expiry}
                      onChange={(e) => patch(r.productId, 'expiry', e.target.value)}
                    />
                  </label>
                </div>
              </li>
            ))}
          </ul>
        )}

        <label className={styles.freight}>
          <span>Freight ₹ (apportioned across lines)</span>
          <input
            type="number"
            min={0}
            step="0.01"
            value={freight}
            onChange={(e) => setFreight(e.target.value)}
          />
        </label>

        <Button
          size="lg"
          onClick={onSubmit}
          isLoading={create.isPending}
          disabled={!canSubmit}
        >
          Receive stock
        </Button>

        {error ? (
          <p role="alert" className={styles.error}>
            {error}
          </p>
        ) : null}
        {result ? (
          <div role="status" className={styles.success}>
            <p>
              Received — <strong>{result.grn}</strong>. Landed unit costs:
            </p>
            <ul>
              {result.costs.map((c) => (
                <li key={c.product_id}>
                  {result.names[c.product_id] ?? c.product_id}:{' '}
                  {formatCurrency(c.landed_unit_cost)}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>
    </div>
  );
}
