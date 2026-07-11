'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Button } from '@/components/ui/Button';
import { ApiError } from '@/lib/api/client';
import { formatCurrency } from '@/lib/formatting/currency';
import type { CustomerType } from './api';
import { useCreateCustomer, useCustomers } from './useCustomers';
import styles from './CustomersPanel.module.scss';

const TYPES: CustomerType[] = ['farmer', 'retail', 'retailer', 'dealer', 'distributor'];

interface FormValues {
  code: string;
  name: string;
  customer_type: CustomerType;
  credit_limit: string;
}

// Customer list (with credit + outstanding) and an inline create form.
export function CustomersPanel() {
  const [search, setSearch] = useState('');
  const { data, isLoading, isError } = useCustomers(search || undefined);
  const createCustomer = useCreateCustomer();
  const [formError, setFormError] = useState<string | null>(null);
  const { register, handleSubmit, reset } = useForm<FormValues>({
    defaultValues: { code: '', name: '', customer_type: 'dealer', credit_limit: '0' },
  });

  const onSubmit = async (values: FormValues) => {
    setFormError(null);
    try {
      await createCustomer.mutateAsync({
        code: values.code.trim(),
        name: values.name.trim(),
        customer_type: values.customer_type,
        credit_limit: values.credit_limit || '0',
      });
      reset();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : 'Could not create customer.');
    }
  };

  return (
    <div className={styles.layout}>
      <section className={styles.listCol}>
        <input
          type="search"
          className={styles.search}
          placeholder="Search by name or code…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search customers"
        />
        {isError ? (
          <p role="alert" className={styles.error}>
            Could not load customers.
          </p>
        ) : isLoading ? (
          <p className={styles.muted}>Loading…</p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className={styles.muted}>No customers found.</p>
        ) : (
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th className={styles.num}>Credit limit</th>
                  <th className={styles.num}>Outstanding</th>
                  <th className={styles.num}>Available</th>
                </tr>
              </thead>
              <tbody>
                {data?.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <span className={styles.name}>{c.name}</span>
                      <span className={styles.code}>{c.code}</span>
                    </td>
                    <td className={styles.type}>{c.customer_type.replace('_', ' ')}</td>
                    <td className={`${styles.num} tabular-nums`}>
                      {formatCurrency(c.credit_limit)}
                    </td>
                    <td className={`${styles.num} tabular-nums`}>
                      {formatCurrency(c.outstanding)}
                    </td>
                    <td
                      className={`${styles.num} tabular-nums ${
                        Number(c.available_credit) < 0 ? styles.negative : ''
                      }`}
                    >
                      {formatCurrency(c.available_credit)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <aside className={styles.formCol}>
        <h3 className={styles.formTitle}>Add customer</h3>
        <form onSubmit={handleSubmit(onSubmit)} className={styles.form} noValidate>
          <label className={styles.field}>
            <span>Code</span>
            <input {...register('code', { required: true })} />
          </label>
          <label className={styles.field}>
            <span>Name</span>
            <input {...register('name', { required: true })} />
          </label>
          <label className={styles.field}>
            <span>Type</span>
            <select {...register('customer_type')}>
              {TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <label className={styles.field}>
            <span>Credit limit (₹)</span>
            <input type="number" min={0} step="0.01" {...register('credit_limit')} />
          </label>
          <Button type="submit" isLoading={createCustomer.isPending}>
            Save customer
          </Button>
          {formError ? (
            <p role="alert" className={styles.error}>
              {formError}
            </p>
          ) : null}
        </form>
      </aside>
    </div>
  );
}
