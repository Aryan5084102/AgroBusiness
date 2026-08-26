'use client';

import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { FieldRow, Input, Select, TextArea } from '@/components/ui/Field';
import { Modal } from '@/components/ui/Modal';
import { useToast } from '@/components/ui/Toast';
import { ApiError } from '@/lib/api/client';
import type { Customer, CustomerType } from './api';
import { useCreateCustomer, useUpdateCustomer } from './useCustomers';
import styles from './CustomersPanel.module.scss';

interface CustomerDialogProps {
  open: boolean;
  /** null = create; otherwise edit this customer. */
  customer: Customer | null;
  onClose: () => void;
}

const TYPES: CustomerType[] = [
  'walk_in',
  'farmer',
  'retail',
  'retailer',
  'dealer',
  'distributor',
  'institution',
];

const EMPTY = {
  code: '',
  name: '',
  customer_type: 'dealer' as CustomerType,
  phone: '',
  gstin: '',
  address: '',
  village: '',
  credit_limit: '0',
  credit_period_days: '30',
};

export function CustomerDialog({ open, customer, onClose }: CustomerDialogProps) {
  const toast = useToast();
  const createCustomer = useCreateCustomer();
  const updateCustomer = useUpdateCustomer();
  const isEdit = customer !== null;

  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setForm(
      customer
        ? {
            code: customer.code,
            name: customer.name,
            customer_type: customer.customer_type,
            phone: customer.phone ?? '',
            gstin: customer.gstin ?? '',
            address: customer.address ?? '',
            village: customer.village ?? '',
            credit_limit: customer.credit_limit,
            credit_period_days: String(customer.credit_period_days),
          }
        : EMPTY,
    );
  }, [open, customer]);

  const set = (field: keyof typeof EMPTY, value: string) =>
    setForm((current) => ({ ...current, [field]: value }));

  const submit = async () => {
    setError(null);
    if (!form.name.trim() || (!isEdit && !form.code.trim())) {
      setError('A code and a name are both required.');
      return;
    }
    const payload = {
      name: form.name.trim(),
      customer_type: form.customer_type,
      phone: form.phone || undefined,
      gstin: form.gstin || undefined,
      address: form.address.trim() || undefined,
      village: form.village || undefined,
      credit_limit: form.credit_limit || '0',
      credit_period_days: Number(form.credit_period_days || 0),
    };
    try {
      if (isEdit && customer) {
        await updateCustomer.mutateAsync({ customerId: customer.id, input: payload });
        toast.success('Customer updated');
      } else {
        await createCustomer.mutateAsync({ code: form.code.trim(), ...payload });
        toast.success('Customer added');
      }
      onClose();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'The customer could not be saved.',
      );
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEdit ? `Edit ${customer?.name}` : 'Add a customer'}
      description="A credit limit above zero lets this customer buy on account; the limit is checked at order time."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={submit}
            isLoading={createCustomer.isPending || updateCustomer.isPending}
          >
            {isEdit ? 'Save changes' : 'Create customer'}
          </Button>
        </>
      }
    >
      <div className={styles.form}>
        <FieldRow>
          <Input
            label="Code"
            required
            disabled={isEdit}
            value={form.code}
            hint={isEdit ? 'Cannot change after creation.' : 'e.g. DLR-GREEN'}
            onChange={(event) => set('code', event.target.value.toUpperCase())}
          />
          <Input
            label="Name"
            required
            value={form.name}
            onChange={(event) => set('name', event.target.value)}
          />
        </FieldRow>

        <FieldRow>
          <Select
            label="Type"
            value={form.customer_type}
            onChange={(event) => set('customer_type', event.target.value)}
          >
            {TYPES.map((type) => (
              <option key={type} value={type}>
                {type.replace(/_/g, ' ')}
              </option>
            ))}
          </Select>
          <Input
            label="Phone"
            value={form.phone}
            onChange={(event) => set('phone', event.target.value)}
          />
        </FieldRow>

        <FieldRow>
          <Input
            label="Credit limit (₹)"
            type="number"
            min="0"
            step="0.01"
            value={form.credit_limit}
            hint="Zero means cash sales only."
            onChange={(event) => set('credit_limit', event.target.value)}
          />
          <Input
            label="Credit period (days)"
            type="number"
            min="0"
            max="365"
            value={form.credit_period_days}
            onChange={(event) => set('credit_period_days', event.target.value)}
          />
        </FieldRow>

        <FieldRow>
          <Input
            label="GSTIN"
            value={form.gstin}
            onChange={(event) => set('gstin', event.target.value)}
          />
          <Input
            label="Village / town"
            value={form.village}
            onChange={(event) => set('village', event.target.value)}
          />
        </FieldRow>

        <TextArea
          label="Address"
          rows={2}
          hint="Printed in the 'billed to' block of this dealer's tax invoice."
          value={form.address}
          onChange={(event) => set('address', event.target.value)}
        />

        {error ? (
          <p role="alert" className={styles.error}>
            {error}
          </p>
        ) : null}
      </div>
    </Modal>
  );
}
