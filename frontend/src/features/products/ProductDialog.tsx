'use client';

import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { FieldRow, Input, Select } from '@/components/ui/Field';
import { Modal } from '@/components/ui/Modal';
import { useToast } from '@/components/ui/Toast';
import { ApiError } from '@/lib/api/client';
import type { Product } from './api';
import {
  useCategories,
  useCreateProduct,
  useUnits,
  useUpdateProduct,
} from './useProducts';
import styles from './ProductsTable.module.scss';

interface ProductDialogProps {
  open: boolean;
  /** null = create a new product; otherwise edit this one. */
  product: Product | null;
  onClose: () => void;
}

const EMPTY = {
  name: '',
  sku: '',
  category_id: '',
  base_unit_id: '',
  barcode: '',
  hsn_code: '',
  retail_price: '0',
  wholesale_price: '0',
  mrp: '0',
  gst_rate: '0',
  min_stock: '0',
  tracks_batches: false,
  tracks_expiry: false,
};

/** One dialog for both creating and editing. SKU, category and unit are fixed
 * after creation because stock and invoices already reference them. */
export function ProductDialog({ open, product, onClose }: ProductDialogProps) {
  const toast = useToast();
  const categories = useCategories(open);
  const units = useUnits(open);
  const createProduct = useCreateProduct();
  const updateProduct = useUpdateProduct();
  const isEdit = product !== null;

  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState<string | null>(null);

  // Load the selected product into the form each time the dialog opens.
  useEffect(() => {
    if (!open) return;
    setError(null);
    setForm(
      product
        ? {
            name: product.name,
            sku: product.sku,
            category_id: product.category_id,
            base_unit_id: product.base_unit_id,
            barcode: product.barcode ?? '',
            hsn_code: product.hsn_code ?? '',
            retail_price: product.retail_price,
            wholesale_price: product.wholesale_price,
            mrp: product.mrp,
            gst_rate: product.gst_rate,
            min_stock: product.min_stock,
            tracks_batches: product.tracks_batches,
            tracks_expiry: product.tracks_expiry,
          }
        : EMPTY,
    );
  }, [open, product]);

  const set = (field: keyof typeof EMPTY, value: string | boolean) =>
    setForm((current) => ({ ...current, [field]: value }));

  const submit = async () => {
    setError(null);
    if (!form.name.trim()) {
      setError('Give the product a name.');
      return;
    }
    try {
      if (isEdit && product) {
        await updateProduct.mutateAsync({
          productId: product.id,
          input: {
            name: form.name,
            barcode: form.barcode || null,
            hsn_code: form.hsn_code || null,
            retail_price: form.retail_price,
            wholesale_price: form.wholesale_price,
            mrp: form.mrp,
            gst_rate: form.gst_rate,
            min_stock: form.min_stock,
          },
        });
        toast.success('Product updated', 'New prices apply to future sales only.');
      } else {
        if (!form.sku.trim() || !form.category_id || !form.base_unit_id) {
          setError('SKU, category and unit are required for a new product.');
          return;
        }
        await createProduct.mutateAsync({
          ...form,
          barcode: form.barcode || null,
          hsn_code: form.hsn_code || null,
        });
        toast.success('Product added', 'Receive stock against it to start selling.');
      }
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The product could not be saved.');
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title={isEdit ? `Edit ${product?.name}` : 'Add a product'}
      description={
        isEdit
          ? 'SKU, category and unit are fixed once stock exists against the product.'
          : 'Create a catalogue entry. Stock arrives later through a goods receipt.'
      }
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={submit}
            isLoading={createProduct.isPending || updateProduct.isPending}
          >
            {isEdit ? 'Save changes' : 'Create product'}
          </Button>
        </>
      }
    >
      <div className={styles.form}>
        <FieldRow>
          <Input
            label="Name"
            required
            value={form.name}
            onChange={(event) => set('name', event.target.value)}
          />
          <Input
            label="SKU"
            required
            disabled={isEdit}
            value={form.sku}
            hint={
              isEdit
                ? 'Cannot change after creation.'
                : 'A unique code, e.g. FERT-UREA-50'
            }
            onChange={(event) => set('sku', event.target.value.toUpperCase())}
          />
        </FieldRow>

        <FieldRow>
          <Select
            label="Category"
            required
            disabled={isEdit}
            value={form.category_id}
            onChange={(event) => set('category_id', event.target.value)}
          >
            <option value="">Select…</option>
            {(categories.data ?? []).map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </Select>
          <Select
            label="Base unit"
            required
            disabled={isEdit}
            value={form.base_unit_id}
            onChange={(event) => set('base_unit_id', event.target.value)}
          >
            <option value="">Select…</option>
            {(units.data ?? []).map((unit) => (
              <option key={unit.id} value={unit.id}>
                {unit.name} ({unit.code})
              </option>
            ))}
          </Select>
        </FieldRow>

        <FieldRow>
          <Input
            label="Retail price"
            type="number"
            min="0"
            step="0.01"
            value={form.retail_price}
            onChange={(event) => set('retail_price', event.target.value)}
          />
          <Input
            label="Wholesale price"
            type="number"
            min="0"
            step="0.01"
            value={form.wholesale_price}
            onChange={(event) => set('wholesale_price', event.target.value)}
          />
          <Input
            label="MRP"
            type="number"
            min="0"
            step="0.01"
            value={form.mrp}
            hint="Selling above MRP is blocked."
            onChange={(event) => set('mrp', event.target.value)}
          />
        </FieldRow>

        <FieldRow>
          <Input
            label="GST %"
            type="number"
            min="0"
            max="100"
            step="0.01"
            value={form.gst_rate}
            onChange={(event) => set('gst_rate', event.target.value)}
          />
          <Input
            label="Reorder level"
            type="number"
            min="0"
            step="0.001"
            value={form.min_stock}
            hint="Below this, the product shows as low stock."
            onChange={(event) => set('min_stock', event.target.value)}
          />
          <Input
            label="HSN code"
            value={form.hsn_code}
            onChange={(event) => set('hsn_code', event.target.value)}
          />
        </FieldRow>

        <Input
          label="Barcode"
          value={form.barcode}
          hint="Optional — scanned at the counter to add the item instantly."
          onChange={(event) => set('barcode', event.target.value)}
        />

        {!isEdit ? (
          <FieldRow>
            <label className={styles.checkbox}>
              <input
                type="checkbox"
                checked={form.tracks_batches}
                onChange={(event) => set('tracks_batches', event.target.checked)}
              />
              Track batches
            </label>
            <label className={styles.checkbox}>
              <input
                type="checkbox"
                checked={form.tracks_expiry}
                onChange={(event) => set('tracks_expiry', event.target.checked)}
              />
              Track expiry (issues earliest-expiry first)
            </label>
          </FieldRow>
        ) : null}

        {error ? (
          <p role="alert" className={styles.error}>
            {error}
          </p>
        ) : null}
      </div>
    </Modal>
  );
}
