'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Button } from '@/components/ui/Button';
import { ApiError } from '@/lib/api/client';
import { useCreateSupplier, useSuppliers } from './useSuppliers';
import styles from './SuppliersPanel.module.scss';

interface FormValues {
  code: string;
  name: string;
  phone: string;
}

// Suppliers list with an inline create form. Server errors are mapped, never raw.
export function SuppliersPanel() {
  const { data, isLoading, isError } = useSuppliers();
  const createSupplier = useCreateSupplier();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ defaultValues: { code: '', name: '', phone: '' } });

  const onSubmit = async (values: FormValues) => {
    setFormError(null);
    try {
      await createSupplier.mutateAsync({
        code: values.code.trim(),
        name: values.name.trim(),
        phone: values.phone.trim() || undefined,
      });
      reset();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : 'Could not create supplier.');
    }
  };

  return (
    <div className={styles.layout}>
      <section className={styles.listCol}>
        {isError ? (
          <p role="alert" className={styles.error}>
            Could not load suppliers.
          </p>
        ) : isLoading ? (
          <p className={styles.muted}>Loading…</p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className={styles.empty}>No suppliers yet. Add your first on the right.</p>
        ) : (
          <ul role="list" className={styles.list}>
            {data?.map((s) => (
              <li key={s.id} className={styles.row}>
                <span className={styles.code}>{s.code}</span>
                <span className={styles.name}>{s.name}</span>
                <span className={s.is_active ? styles.active : styles.inactive}>
                  {s.is_active ? 'Active' : 'Inactive'}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <aside className={styles.formCol}>
        <h3 className={styles.formTitle}>Add supplier</h3>
        <form onSubmit={handleSubmit(onSubmit)} className={styles.form} noValidate>
          <label className={styles.field}>
            <span>Code</span>
            <input
              {...register('code', { required: true })}
              aria-invalid={!!errors.code}
            />
          </label>
          <label className={styles.field}>
            <span>Name</span>
            <input
              {...register('name', { required: true })}
              aria-invalid={!!errors.name}
            />
          </label>
          <label className={styles.field}>
            <span>Phone (optional)</span>
            <input {...register('phone')} />
          </label>
          <Button type="submit" isLoading={createSupplier.isPending}>
            Save supplier
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
