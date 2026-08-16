'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { FieldRow, Select, TextArea } from '@/components/ui/Field';
import { Modal } from '@/components/ui/Modal';
import { useToast } from '@/components/ui/Toast';
import { useCustomers } from '@/features/customers/useCustomers';
import { useProducts } from '@/features/products/useProducts';
import { useWarehouses } from '@/features/settings/useSettings';
import { ApiError } from '@/lib/api/client';
import { useCreateJob } from './useService';

interface NewJobDialogProps {
  open: boolean;
  onClose: () => void;
  onCreated?: (jobId: string) => void;
}

/** Books a machine in for repair and issues its job number. */
export function NewJobDialog({ open, onClose, onCreated }: NewJobDialogProps) {
  const toast = useToast();
  const warehouses = useWarehouses(open);
  const customers = useCustomers({ enabled: open });
  const products = useProducts({ limit: 100 }, open);
  const createJob = useCreateJob();

  const [warehouseId, setWarehouseId] = useState('');
  const [customerId, setCustomerId] = useState('');
  const [productId, setProductId] = useState('');
  const [complaint, setComplaint] = useState('');
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setError(null);
    const warehouse = warehouseId || warehouses.data?.[0]?.id;
    if (!warehouse) {
      setError('Choose the workshop or shop the machine is held at.');
      return;
    }
    try {
      const job = await createJob.mutateAsync({
        warehouseId: warehouse,
        customerId: customerId || null,
        productId: productId || null,
        complaint: complaint.trim() || undefined,
      });
      toast.success(`Job ${job.job_number} created`, 'Add parts and labour as you work.');
      setComplaint('');
      setProductId('');
      setCustomerId('');
      onClose();
      onCreated?.(job.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The job could not be created.');
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Book a machine in"
      description="Creates a numbered repair job. Warranty cover is detected automatically for serialised machines."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} isLoading={createJob.isPending}>
            Create job
          </Button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        <FieldRow>
          <Select
            label="Held at"
            required
            value={warehouseId}
            onChange={(event) => setWarehouseId(event.target.value)}
          >
            <option value="">Select…</option>
            {(warehouses.data ?? []).map((warehouse) => (
              <option key={warehouse.id} value={warehouse.id}>
                {warehouse.name}
              </option>
            ))}
          </Select>
          <Select
            label="Customer"
            value={customerId}
            onChange={(event) => setCustomerId(event.target.value)}
          >
            <option value="">Not recorded</option>
            {(customers.data ?? []).map((customer) => (
              <option key={customer.id} value={customer.id}>
                {customer.name}
              </option>
            ))}
          </Select>
        </FieldRow>

        <Select
          label="Machine"
          value={productId}
          onChange={(event) => setProductId(event.target.value)}
          hint="Pick the catalogue item this machine matches, if you sell it."
        >
          <option value="">Not recorded</option>
          {(products.data?.items ?? []).map((product) => (
            <option key={product.id} value={product.id}>
              {product.name}
            </option>
          ))}
        </Select>

        <TextArea
          label="Reported problem"
          value={complaint}
          placeholder="e.g. Sprayer not building pressure; leaking at the nozzle"
          onChange={(event) => setComplaint(event.target.value)}
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
