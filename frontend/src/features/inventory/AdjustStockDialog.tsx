'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { FieldRow, Input, Select, TextArea } from '@/components/ui/Field';
import { Modal } from '@/components/ui/Modal';
import { useToast } from '@/components/ui/Toast';
import { useProducts } from '@/features/products/useProducts';
import { useWarehouses } from '@/features/settings/useSettings';
import { ApiError } from '@/lib/api/client';
import { useCreateAdjustment } from './useInventory';
import type { AdjustmentInput } from './api';

interface AdjustStockDialogProps {
  open: boolean;
  onClose: () => void;
}

type MovementKind = AdjustmentInput['movementType'];

const KINDS: { value: MovementKind; label: string; hint: string }[] = [
  {
    value: 'adjustment',
    label: 'Correction',
    hint: 'Use a negative quantity to reduce stock, positive to add it.',
  },
  {
    value: 'reconciliation',
    label: 'Stock count',
    hint: 'Difference found during a count.',
  },
  { value: 'damage', label: 'Damage', hint: 'Quantity damaged and written off.' },
  { value: 'expiry', label: 'Expiry', hint: 'Quantity discarded because it expired.' },
];

/** Posts a signed correction to the stock ledger. A reason is mandatory —
 * every adjustment is attributable in the ledger and the audit trail. */
export function AdjustStockDialog({ open, onClose }: AdjustStockDialogProps) {
  const toast = useToast();
  const warehouses = useWarehouses(open);
  const products = useProducts({ limit: 100 }, open);
  const adjust = useCreateAdjustment();

  const [warehouseId, setWarehouseId] = useState('');
  const [productId, setProductId] = useState('');
  const [kind, setKind] = useState<MovementKind>('adjustment');
  const [quantity, setQuantity] = useState('');
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);

  const selectedKind = KINDS.find((k) => k.value === kind);
  const isSigned = kind === 'adjustment' || kind === 'reconciliation';

  const reset = () => {
    setQuantity('');
    setReason('');
    setError(null);
  };

  const submit = async () => {
    setError(null);
    const warehouse = warehouseId || warehouses.data?.[0]?.id;
    if (!warehouse || !productId) {
      setError('Choose a warehouse and a product.');
      return;
    }
    if (!quantity || Number(quantity) === 0) {
      setError('Enter a non-zero quantity.');
      return;
    }
    if (reason.trim().length < 3) {
      setError('Give a reason — it is recorded permanently against this movement.');
      return;
    }
    try {
      await adjust.mutateAsync({
        warehouseId: warehouse,
        productId,
        signedQuantity: quantity,
        reason: reason.trim(),
        movementType: kind,
      });
      toast.success('Stock adjusted', 'The movement is recorded in the ledger.');
      reset();
      onClose();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'The adjustment could not be posted.',
      );
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Adjust stock"
      description="Corrections are posted as new ledger entries — existing movements are never edited."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} isLoading={adjust.isPending}>
            Post adjustment
          </Button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        <FieldRow>
          <Select
            label="Warehouse"
            required
            value={warehouseId}
            onChange={(event) => setWarehouseId(event.target.value)}
          >
            <option value="">Select a warehouse…</option>
            {(warehouses.data ?? []).map((warehouse) => (
              <option key={warehouse.id} value={warehouse.id}>
                {warehouse.name}
              </option>
            ))}
          </Select>
          <Select
            label="Reason type"
            value={kind}
            onChange={(event) => setKind(event.target.value as MovementKind)}
          >
            {KINDS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </FieldRow>

        <Select
          label="Product"
          required
          value={productId}
          onChange={(event) => setProductId(event.target.value)}
        >
          <option value="">Select a product…</option>
          {(products.data?.items ?? []).map((product) => (
            <option key={product.id} value={product.id}>
              {product.name} ({product.sku})
            </option>
          ))}
        </Select>

        <Input
          label={isSigned ? 'Quantity (+ adds, − removes)' : 'Quantity to write off'}
          required
          type="number"
          step="0.001"
          value={quantity}
          hint={selectedKind?.hint}
          onChange={(event) => setQuantity(event.target.value)}
        />

        <TextArea
          label="Reason"
          required
          value={reason}
          placeholder="e.g. Physical count on 11 Aug found 3 bags short"
          onChange={(event) => setReason(event.target.value)}
        />

        {error ? (
          <p role="alert" style={{ color: 'var(--color-danger)', fontSize: 13 }}>
            {error}
          </p>
        ) : null}
      </div>
    </Modal>
  );
}
