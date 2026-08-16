'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { FieldRow, Input, Select } from '@/components/ui/Field';
import { Modal } from '@/components/ui/Modal';
import { useToast } from '@/components/ui/Toast';
import { useProducts } from '@/features/products/useProducts';
import { useWarehouses } from '@/features/settings/useSettings';
import { ApiError } from '@/lib/api/client';
import { useCreateTransfer } from './useInventory';

interface TransferStockDialogProps {
  open: boolean;
  onClose: () => void;
}

/** Moves stock between warehouses as a paired OUT/IN in one transaction, so the
 * two sides can never drift apart. */
export function TransferStockDialog({ open, onClose }: TransferStockDialogProps) {
  const toast = useToast();
  const warehouses = useWarehouses(open);
  const products = useProducts({ limit: 100 }, open);
  const transfer = useCreateTransfer();

  const [fromId, setFromId] = useState('');
  const [toId, setToId] = useState('');
  const [productId, setProductId] = useState('');
  const [quantity, setQuantity] = useState('');
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setError(null);
    if (!fromId || !toId || !productId) {
      setError('Choose both warehouses and a product.');
      return;
    }
    if (fromId === toId) {
      setError('Source and destination must be different warehouses.');
      return;
    }
    if (!quantity || Number(quantity) <= 0) {
      setError('Enter a quantity greater than zero.');
      return;
    }
    try {
      await transfer.mutateAsync({
        fromWarehouseId: fromId,
        toWarehouseId: toId,
        productId,
        baseQuantity: quantity,
      });
      toast.success('Stock transferred', 'Both warehouses have been updated.');
      setQuantity('');
      onClose();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'The transfer could not be completed.',
      );
    }
  };

  const options = warehouses.data ?? [];

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Transfer stock"
      description="Move goods from the godown to the shop counter, or between branches."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} isLoading={transfer.isPending}>
            Transfer
          </Button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        <FieldRow>
          <Select
            label="From"
            required
            value={fromId}
            onChange={(event) => setFromId(event.target.value)}
          >
            <option value="">Select…</option>
            {options.map((warehouse) => (
              <option key={warehouse.id} value={warehouse.id}>
                {warehouse.name}
              </option>
            ))}
          </Select>
          <Select
            label="To"
            required
            value={toId}
            onChange={(event) => setToId(event.target.value)}
          >
            <option value="">Select…</option>
            {options.map((warehouse) => (
              <option key={warehouse.id} value={warehouse.id}>
                {warehouse.name}
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
          label="Quantity"
          required
          type="number"
          min="0"
          step="0.001"
          value={quantity}
          hint="In the product's base unit. The transfer fails if the source lacks the stock."
          onChange={(event) => setQuantity(event.target.value)}
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
