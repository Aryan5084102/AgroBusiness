'use client';

import { useState } from 'react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { DataTable } from '@/components/ui/DataTable';
import { FieldRow, Input } from '@/components/ui/Field';
import { Modal } from '@/components/ui/Modal';
import { QueryState } from '@/components/feedback/QueryState';
import { useToast } from '@/components/ui/Toast';
import { usePermissions } from '@/features/auth/usePermissions';
import { ApiError } from '@/lib/api/client';
import type { Supplier } from './api';
import { useCreateSupplier, useSuppliers } from './useSuppliers';
import styles from './SuppliersPanel.module.scss';

/** The supplier book. Adding one requires `purchase.create` — the same
 * permission as booking a delivery in. */
export function SuppliersPanel() {
  const { can } = usePermissions();
  const suppliers = useSuppliers();
  const [creating, setCreating] = useState(false);

  return (
    <>
      <Card>
        <CardHeader
          title="Suppliers"
          description="Who you buy from. Duplicate supplier invoices are rejected automatically."
          actions={
            can('purchase.create') ? (
              <Button size="sm" icon="plus" onClick={() => setCreating(true)}>
                Add supplier
              </Button>
            ) : null
          }
        />
        <QueryState
          isLoading={suppliers.isLoading}
          error={suppliers.error}
          onRetry={suppliers.refetch}
          loadingHeight={200}
        >
          <DataTable<Supplier>
            rows={suppliers.data ?? []}
            rowKey={(row) => row.id}
            emptyTitle="No suppliers yet"
            emptyDescription="Add the businesses you buy stock from."
            emptyAction={
              can('purchase.create') ? (
                <Button size="sm" icon="plus" onClick={() => setCreating(true)}>
                  Add supplier
                </Button>
              ) : null
            }
            columns={[
              {
                key: 'name',
                header: 'Supplier',
                render: (row) => (
                  <span className={styles.primaryCell}>
                    <span>{row.name}</span>
                    <span className={styles.muted}>{row.code}</span>
                  </span>
                ),
              },
              {
                key: 'status',
                header: 'Status',
                render: (row) =>
                  row.is_active ? (
                    <Badge tone="success" dot>
                      Active
                    </Badge>
                  ) : (
                    <Badge tone="neutral" dot>
                      Inactive
                    </Badge>
                  ),
              },
            ]}
          />
        </QueryState>
      </Card>

      <NewSupplierDialog open={creating} onClose={() => setCreating(false)} />
    </>
  );
}

function NewSupplierDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const toast = useToast();
  const createSupplier = useCreateSupplier();
  const [form, setForm] = useState({ code: '', name: '', phone: '', gstin: '' });
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setError(null);
    if (!form.code.trim() || !form.name.trim()) {
      setError('A code and a name are both required.');
      return;
    }
    try {
      await createSupplier.mutateAsync({
        code: form.code.trim(),
        name: form.name.trim(),
        phone: form.phone.trim() || undefined,
        gstin: form.gstin.trim() || undefined,
      });
      toast.success('Supplier added');
      setForm({ code: '', name: '', phone: '', gstin: '' });
      onClose();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'The supplier could not be saved.',
      );
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add a supplier"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} isLoading={createSupplier.isPending}>
            Save supplier
          </Button>
        </>
      }
    >
      <div className={styles.form}>
        <FieldRow>
          <Input
            label="Code"
            required
            value={form.code}
            hint="e.g. SUP-IFFCO"
            onChange={(event) =>
              setForm({ ...form, code: event.target.value.toUpperCase() })
            }
          />
          <Input
            label="Name"
            required
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        </FieldRow>
        <FieldRow>
          <Input
            label="Phone"
            value={form.phone}
            onChange={(event) => setForm({ ...form, phone: event.target.value })}
          />
          <Input
            label="GSTIN"
            value={form.gstin}
            onChange={(event) => setForm({ ...form, gstin: event.target.value })}
          />
        </FieldRow>
        {error ? (
          <p role="alert" className={styles.error}>
            {error}
          </p>
        ) : null}
      </div>
    </Modal>
  );
}
