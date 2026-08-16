'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { FieldRow, Input, Select } from '@/components/ui/Field';
import { Modal } from '@/components/ui/Modal';
import { useToast } from '@/components/ui/Toast';
import { ApiError } from '@/lib/api/client';
import type { Role } from './api';
import { useBranches, useCreateUser } from './useSettings';
import styles from './SettingsScreen.module.scss';

interface NewUserDialogProps {
  open: boolean;
  onClose: () => void;
  roles: Role[];
}

/** Creates a staff account with exactly one role — the role decides every
 * screen and action that person gets. */
export function NewUserDialog({ open, onClose, roles }: NewUserDialogProps) {
  const toast = useToast();
  const branches = useBranches(open);
  const createUser = useCreateUser();

  const [form, setForm] = useState({
    full_name: '',
    email: '',
    password: '',
    role_code: '',
    branch_id: '',
  });
  const [error, setError] = useState<string | null>(null);

  const selectedRole = roles.find((role) => role.code === form.role_code);

  const submit = async () => {
    setError(null);
    if (!form.full_name || !form.email || !form.role_code) {
      setError('Name, email and role are all required.');
      return;
    }
    if (form.password.length < 8) {
      setError('The password must be at least 8 characters.');
      return;
    }
    try {
      await createUser.mutateAsync({
        full_name: form.full_name,
        email: form.email,
        password: form.password,
        role_code: form.role_code,
        branch_id: form.branch_id || null,
      });
      toast.success(
        'Account created',
        `${form.full_name} can now sign in with the ${selectedRole?.name ?? 'assigned'} role.`,
      );
      setForm({ full_name: '', email: '', password: '', role_code: '', branch_id: '' });
      onClose();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'The account could not be created.',
      );
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add a person"
      description="They will sign in with this email and password, and see only what their role allows."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} isLoading={createUser.isPending}>
            Create account
          </Button>
        </>
      }
    >
      <div className={styles.form}>
        <FieldRow>
          <Input
            label="Full name"
            required
            value={form.full_name}
            onChange={(event) => setForm({ ...form, full_name: event.target.value })}
          />
          <Input
            label="Email"
            type="email"
            required
            autoComplete="off"
            value={form.email}
            onChange={(event) => setForm({ ...form, email: event.target.value })}
          />
        </FieldRow>

        <Input
          label="Temporary password"
          type="password"
          required
          autoComplete="new-password"
          value={form.password}
          hint="At least 8 characters. Ask them to change it after the first sign-in."
          onChange={(event) => setForm({ ...form, password: event.target.value })}
        />

        <FieldRow>
          <Select
            label="Role"
            required
            value={form.role_code}
            onChange={(event) => setForm({ ...form, role_code: event.target.value })}
          >
            <option value="">Select a role…</option>
            {roles
              .filter((role) => role.code !== 'owner')
              .map((role) => (
                <option key={role.code} value={role.code}>
                  {role.name}
                </option>
              ))}
          </Select>
          <Select
            label="Branch"
            value={form.branch_id}
            onChange={(event) => setForm({ ...form, branch_id: event.target.value })}
          >
            <option value="">All branches</option>
            {(branches.data ?? []).map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name}
              </option>
            ))}
          </Select>
        </FieldRow>

        {selectedRole ? (
          <p className={styles.roleHint}>
            {selectedRole.name} holds {selectedRole.permissions.length} permissions.
          </p>
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
