'use client';

import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { Icon } from '@/components/ui/Icon';
import { Input, Select } from '@/components/ui/Field';
import { useToast } from '@/components/ui/Toast';
import { ProductPicker } from '@/features/pos/ProductPicker';
import { useWarehouses } from '@/features/settings/useSettings';
import { ApiError } from '@/lib/api/client';
import { formatCurrency } from '@/lib/formatting/currency';
import { useCreateGoodsReceipt, useSupplierOptions } from './useGoodsReceipt';
import styles from './GoodsReceiptScreen.module.scss';

interface ReceiptRow {
  productId: string;
  name: string;
  quantity: string;
  rate: string;
  free: string;
  batch: string;
  expiry: string;
}

/**
 * Books a supplier delivery into stock. Freight and other charges are spread
 * across the lines by value, so each product's landed cost reflects what it
 * really cost to get on the shelf.
 */
export function GoodsReceiptScreen() {
  const toast = useToast();
  const warehouses = useWarehouses();
  const suppliers = useSupplierOptions();
  const create = useCreateGoodsReceipt();

  const [warehouseId, setWarehouseId] = useState('');
  const [supplierId, setSupplierId] = useState('');
  const [freight, setFreight] = useState('0');
  const [otherCharges, setOtherCharges] = useState('0');
  const [rows, setRows] = useState<ReceiptRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!warehouseId && warehouses.data && warehouses.data.length > 0) {
      // Default to a godown when there is one — bulk deliveries land there.
      const godown = warehouses.data.find((w) => w.type === 'godown');
      setWarehouseId((godown ?? warehouses.data[0]!).id);
    }
  }, [warehouseId, warehouses.data]);

  const addProduct = (productId: string, name: string) => {
    setRows((prev) =>
      prev.some((row) => row.productId === productId)
        ? prev
        : [
            ...prev,
            {
              productId,
              name,
              quantity: '1',
              rate: '0',
              free: '0',
              batch: '',
              expiry: '',
            },
          ],
    );
  };

  const patch = (productId: string, field: keyof ReceiptRow, value: string) =>
    setRows((prev) =>
      prev.map((row) => (row.productId === productId ? { ...row, [field]: value } : row)),
    );

  const removeRow = (productId: string) =>
    setRows((prev) => prev.filter((row) => row.productId !== productId));

  const goodsValue = rows.reduce(
    (total, row) => total + Number(row.quantity || 0) * Number(row.rate || 0),
    0,
  );
  const totalCost = goodsValue + Number(freight || 0) + Number(otherCharges || 0);

  const canSubmit =
    Boolean(warehouseId) &&
    Boolean(supplierId) &&
    rows.length > 0 &&
    rows.every((row) => Number(row.quantity) > 0);

  const onSubmit = async () => {
    if (!canSubmit) return;
    setError(null);
    try {
      const result = await create.mutateAsync({
        warehouseId,
        supplierId,
        freight,
        otherCharges,
        lines: rows.map((row) => ({
          product_id: row.productId,
          received_base_quantity: row.quantity,
          unit_rate: row.rate || '0',
          free_base_quantity: row.free || '0',
          batch_number: row.batch || undefined,
          expiry_date: row.expiry || undefined,
        })),
      });
      toast.success(
        `Received — ${result.grn_number}`,
        `${rows.length} line(s) added to stock at ${formatCurrency(totalCost)} landed cost.`,
      );
      setRows([]);
      setFreight('0');
      setOtherCharges('0');
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : 'The receipt could not be saved.';
      setError(message);
      toast.error('Receipt not saved', message);
    }
  };

  return (
    <div className={styles.layout}>
      <div className={styles.left}>
        <Card>
          <CardBody>
            <div className={styles.contextRow}>
              <Select
                label="Receive into"
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
                label="Supplier"
                required
                value={supplierId}
                onChange={(event) => setSupplierId(event.target.value)}
              >
                <option value="">Select a supplier…</option>
                {(suppliers.data ?? []).map((supplier) => (
                  <option key={supplier.id} value={supplier.id}>
                    {supplier.name} ({supplier.code})
                  </option>
                ))}
              </Select>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Add items to the delivery"
            description="Search the catalogue, then set the quantity, rate and batch for each line."
          />
          <CardBody>
            <ProductPicker onAdd={addProduct} />
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader
          title="Delivery lines"
          actions={
            rows.length > 0 ? (
              <Button variant="ghost" size="sm" icon="trash" onClick={() => setRows([])}>
                Clear
              </Button>
            ) : null
          }
        />
        <CardBody>
          <div className={styles.panel}>
            {rows.length === 0 ? (
              <EmptyState
                icon="purchases"
                title="Nothing added yet"
                description="Search the catalogue and pick a product to add it to this delivery."
              />
            ) : (
              <ul role="list" className={styles.rows}>
                {rows.map((row) => (
                  <li key={row.productId} className={styles.rowItem}>
                    <div className={styles.rowHead}>
                      <span className={styles.rowName}>{row.name}</span>
                      <button
                        type="button"
                        className={styles.remove}
                        aria-label={`Remove ${row.name}`}
                        onClick={() => removeRow(row.productId)}
                      >
                        <Icon name="close" size={15} />
                      </button>
                    </div>
                    <div className={styles.fields}>
                      <Input
                        label="Qty"
                        type="number"
                        min="0"
                        step="0.001"
                        value={row.quantity}
                        onChange={(event) =>
                          patch(row.productId, 'quantity', event.target.value)
                        }
                      />
                      <Input
                        label="Rate ₹"
                        type="number"
                        min="0"
                        step="0.01"
                        value={row.rate}
                        onChange={(event) =>
                          patch(row.productId, 'rate', event.target.value)
                        }
                      />
                      <Input
                        label="Free qty"
                        type="number"
                        min="0"
                        step="0.001"
                        value={row.free}
                        onChange={(event) =>
                          patch(row.productId, 'free', event.target.value)
                        }
                      />
                    </div>
                    <div className={styles.fields}>
                      <Input
                        label="Batch no."
                        value={row.batch}
                        onChange={(event) =>
                          patch(row.productId, 'batch', event.target.value)
                        }
                      />
                      <Input
                        label="Expiry"
                        type="date"
                        value={row.expiry}
                        onChange={(event) =>
                          patch(row.productId, 'expiry', event.target.value)
                        }
                      />
                    </div>
                  </li>
                ))}
              </ul>
            )}

            <div className={styles.charges}>
              <Input
                label="Freight ₹"
                type="number"
                min="0"
                step="0.01"
                value={freight}
                onChange={(event) => setFreight(event.target.value)}
              />
              <Input
                label="Other charges ₹"
                type="number"
                min="0"
                step="0.01"
                value={otherCharges}
                onChange={(event) => setOtherCharges(event.target.value)}
              />
            </div>

            <dl className={styles.totals}>
              <div>
                <dt>Goods value</dt>
                <dd className="tabular-nums">{formatCurrency(goodsValue)}</dd>
              </div>
              <div className={styles.grand}>
                <dt>Landed total</dt>
                <dd className="tabular-nums">{formatCurrency(totalCost)}</dd>
              </div>
            </dl>

            <Button
              size="lg"
              icon="check"
              onClick={onSubmit}
              isLoading={create.isPending}
              disabled={!canSubmit}
            >
              Receive into stock
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
  );
}
