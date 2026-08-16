'use client';

import { useState } from 'react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { DataTable } from '@/components/ui/DataTable';
import { FieldRow, Input, Select } from '@/components/ui/Field';
import { Modal } from '@/components/ui/Modal';
import { QueryState } from '@/components/feedback/QueryState';
import { Tabs } from '@/components/ui/Tabs';
import { useToast } from '@/components/ui/Toast';
import { usePermissions } from '@/features/auth/usePermissions';
import { PERMISSION_LABELS } from '@/features/auth/permissions';
import { ApiError } from '@/lib/api/client';
import { formatDateTime } from '@/lib/formatting/dates';
import { NewUserDialog } from './NewUserDialog';
import type { Branch, OrgUser, Role, Warehouse } from './api';
import {
  useBranches,
  useCreateBranch,
  useCreateWarehouse,
  useOrgProfile,
  useRoles,
  useUpdateOrgProfile,
  useUpdateUser,
  useUsers,
  useWarehouses,
} from './useSettings';
import styles from './SettingsScreen.module.scss';

type Tab = 'business' | 'people' | 'roles' | 'locations';

/** Administration: business identity, staff accounts, the role/permission
 * matrix, and branch/warehouse structure. */
export function SettingsScreen() {
  const { can } = usePermissions();
  const canManageUsers = can('user.manage');
  const canManageSettings = can('settings.manage');

  const [tab, setTab] = useState<Tab>(canManageSettings ? 'business' : 'people');

  const tabs = [
    ...(canManageSettings
      ? [{ id: 'business' as const, label: 'Business', icon: 'settings' as const }]
      : []),
    ...(canManageUsers
      ? [
          { id: 'people' as const, label: 'People', icon: 'user' as const },
          { id: 'roles' as const, label: 'Roles & access', icon: 'lock' as const },
        ]
      : []),
    {
      id: 'locations' as const,
      label: 'Branches & warehouses',
      icon: 'warehouse' as const,
    },
  ];

  return (
    <>
      <Tabs<Tab> label="Settings sections" active={tab} onChange={setTab} items={tabs} />
      {tab === 'business' ? <BusinessPanel /> : null}
      {tab === 'people' ? <PeoplePanel /> : null}
      {tab === 'roles' ? <RolesPanel /> : null}
      {tab === 'locations' ? <LocationsPanel canManage={canManageSettings} /> : null}
    </>
  );
}

function BusinessPanel() {
  const toast = useToast();
  const profile = useOrgProfile();
  const update = useUpdateOrgProfile();
  const [form, setForm] = useState<Record<string, string> | null>(null);

  const current = form ?? {
    name: profile.data?.name ?? '',
    legal_name: profile.data?.legal_name ?? '',
    gstin: profile.data?.gstin ?? '',
    address: profile.data?.address ?? '',
  };

  const save = async () => {
    try {
      await update.mutateAsync(current);
      toast.success('Business details saved', 'These appear on invoices and reports.');
    } catch (err) {
      toast.error(
        'Could not save',
        err instanceof ApiError ? err.message : 'Please try again.',
      );
    }
  };

  return (
    <Card>
      <CardHeader
        title="Business details"
        description="Your name, GSTIN and address. Branding is configurable — nothing is hardcoded."
      />
      <CardBody>
        <QueryState
          isLoading={profile.isLoading}
          error={profile.error}
          onRetry={profile.refetch}
        >
          <div className={styles.form}>
            <FieldRow>
              <Input
                label="Trading name"
                value={current.name}
                onChange={(event) => setForm({ ...current, name: event.target.value })}
              />
              <Input
                label="Legal name"
                value={current.legal_name}
                onChange={(event) =>
                  setForm({ ...current, legal_name: event.target.value })
                }
              />
            </FieldRow>
            <FieldRow>
              <Input
                label="GSTIN"
                value={current.gstin}
                hint="Printed on every tax invoice."
                onChange={(event) => setForm({ ...current, gstin: event.target.value })}
              />
              <Input
                label="Currency"
                value={profile.data?.currency ?? 'INR'}
                disabled
                hint="Set at organization creation."
              />
            </FieldRow>
            <Input
              label="Address"
              value={current.address}
              onChange={(event) => setForm({ ...current, address: event.target.value })}
            />
            <div>
              <Button onClick={save} isLoading={update.isPending}>
                Save changes
              </Button>
            </div>
          </div>
        </QueryState>
      </CardBody>
    </Card>
  );
}

function PeoplePanel() {
  const toast = useToast();
  const users = useUsers();
  const roles = useRoles();
  const updateUser = useUpdateUser();
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<OrgUser | null>(null);

  const toggleActive = async (user: OrgUser) => {
    try {
      await updateUser.mutateAsync({
        userId: user.id,
        input: { is_active: !user.is_active },
      });
      toast.success(user.is_active ? 'Account deactivated' : 'Account reactivated');
    } catch (err) {
      toast.error(
        'Could not update',
        err instanceof ApiError ? err.message : 'Please try again.',
      );
    }
  };

  return (
    <>
      <Card>
        <CardHeader
          title="Staff accounts"
          description="Everyone who can sign in, and the role that decides what they see."
          actions={
            <Button size="sm" icon="plus" onClick={() => setCreating(true)}>
              Add a person
            </Button>
          }
        />
        <QueryState
          isLoading={users.isLoading}
          error={users.error}
          onRetry={users.refetch}
          loadingHeight={240}
        >
          <DataTable<OrgUser>
            rows={users.data ?? []}
            rowKey={(row) => row.id}
            emptyTitle="No staff accounts"
            columns={[
              {
                key: 'name',
                header: 'Person',
                render: (row) => (
                  <span className={styles.primaryCell}>
                    <span>{row.full_name}</span>
                    <span className={styles.muted}>{row.email}</span>
                  </span>
                ),
              },
              {
                key: 'role',
                header: 'Role',
                render: (row) =>
                  row.is_owner ? (
                    <Badge tone="brand">Owner</Badge>
                  ) : (
                    <Badge tone="info">{row.role_name ?? 'No role'}</Badge>
                  ),
              },
              {
                key: 'lastLogin',
                header: 'Last sign-in',
                secondary: true,
                render: (row) => formatDateTime(row.last_login_at),
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
                      Disabled
                    </Badge>
                  ),
              },
              {
                key: 'actions',
                header: '',
                render: (row) => (
                  <span className={styles.rowActions}>
                    <Button variant="ghost" size="sm" onClick={() => setEditing(row)}>
                      Edit
                    </Button>
                    {row.is_owner ? null : (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => toggleActive(row)}
                        disabled={updateUser.isPending}
                      >
                        {row.is_active ? 'Disable' : 'Enable'}
                      </Button>
                    )}
                  </span>
                ),
              },
            ]}
          />
        </QueryState>
      </Card>

      <NewUserDialog
        open={creating}
        onClose={() => setCreating(false)}
        roles={roles.data ?? []}
      />
      <EditUserDialog
        user={editing}
        roles={roles.data ?? []}
        onClose={() => setEditing(null)}
      />
    </>
  );
}

function EditUserDialog({
  user,
  roles,
  onClose,
}: {
  user: OrgUser | null;
  roles: Role[];
  onClose: () => void;
}) {
  const toast = useToast();
  const updateUser = useUpdateUser();
  const [fullName, setFullName] = useState('');
  const [roleCode, setRoleCode] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);

  // Seed the form the first time this user opens in the dialog.
  const activeName = fullName || user?.full_name || '';
  const activeRole = roleCode || user?.role_code || '';

  const save = async () => {
    if (!user) return;
    setError(null);
    if (password && password.length < 8) {
      setError('A new password must be at least 8 characters.');
      return;
    }
    try {
      await updateUser.mutateAsync({
        userId: user.id,
        input: {
          full_name: activeName,
          ...(user.is_owner ? {} : { role_code: activeRole }),
          ...(password ? { password } : {}),
        },
      });
      toast.success('Account updated');
      setFullName('');
      setRoleCode('');
      setPassword('');
      onClose();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'The account could not be updated.',
      );
    }
  };

  return (
    <Modal
      open={Boolean(user)}
      onClose={onClose}
      title={user ? `Edit ${user.full_name}` : 'Edit account'}
      description="Change the name, switch the role, or set a new password."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={save} isLoading={updateUser.isPending}>
            Save
          </Button>
        </>
      }
    >
      <div className={styles.form}>
        <Input
          label="Full name"
          value={activeName}
          onChange={(event) => setFullName(event.target.value)}
        />
        <Select
          label="Role"
          value={activeRole}
          disabled={user?.is_owner}
          hint={user?.is_owner ? 'The owner always holds every permission.' : undefined}
          onChange={(event) => setRoleCode(event.target.value)}
        >
          <option value="">Select a role…</option>
          {roles.map((role) => (
            <option key={role.code} value={role.code}>
              {role.name}
            </option>
          ))}
        </Select>
        <Input
          label="New password"
          type="password"
          value={password}
          autoComplete="new-password"
          hint="Leave blank to keep the current password."
          onChange={(event) => setPassword(event.target.value)}
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

function RolesPanel() {
  const roles = useRoles();

  return (
    <Card>
      <CardHeader
        title="Roles & access"
        description="What each role can do. The backend enforces these on every request — the interface only hides what a role cannot use."
      />
      <QueryState
        isLoading={roles.isLoading}
        error={roles.error}
        onRetry={roles.refetch}
        loadingHeight={280}
      >
        <DataTable<Role>
          rows={roles.data ?? []}
          rowKey={(row) => row.id}
          emptyTitle="No roles defined"
          columns={[
            {
              key: 'role',
              header: 'Role',
              render: (row) => (
                <span className={styles.primaryCell}>
                  <span>{row.name}</span>
                  <span className={styles.muted}>
                    {row.user_count} {row.user_count === 1 ? 'person' : 'people'}
                  </span>
                </span>
              ),
            },
            {
              key: 'permissions',
              header: 'Permissions',
              render: (row) => (
                <div className={styles.permissions}>
                  {row.permissions.map((code) => (
                    <Badge key={code} tone="neutral">
                      {PERMISSION_LABELS[code] ?? code}
                    </Badge>
                  ))}
                </div>
              ),
            },
            {
              key: 'count',
              header: 'Total',
              numeric: true,
              secondary: true,
              render: (row) => `${row.permissions.length} permissions`,
            },
          ]}
        />
      </QueryState>
    </Card>
  );
}

function LocationsPanel({ canManage }: { canManage: boolean }) {
  const toast = useToast();
  const branches = useBranches();
  const warehouses = useWarehouses();
  const createBranch = useCreateBranch();
  const createWarehouse = useCreateWarehouse();

  const [branchForm, setBranchForm] = useState({ name: '', code: '' });
  const [warehouseForm, setWarehouseForm] = useState({
    name: '',
    code: '',
    type: 'shop' as 'shop' | 'godown',
    branch_id: '',
  });

  const addBranch = async () => {
    try {
      await createBranch.mutateAsync(branchForm);
      toast.success('Branch added');
      setBranchForm({ name: '', code: '' });
    } catch (err) {
      toast.error(
        'Could not add branch',
        err instanceof ApiError ? err.message : 'Please try again.',
      );
    }
  };

  const addWarehouse = async () => {
    try {
      await createWarehouse.mutateAsync({
        ...warehouseForm,
        branch_id: warehouseForm.branch_id || null,
      });
      toast.success('Warehouse added');
      setWarehouseForm({ name: '', code: '', type: 'shop', branch_id: '' });
    } catch (err) {
      toast.error(
        'Could not add warehouse',
        err instanceof ApiError ? err.message : 'Please try again.',
      );
    }
  };

  return (
    <div className={styles.stack}>
      <Card>
        <CardHeader
          title="Branches"
          description="Each branch issues its own document numbers."
        />
        <QueryState
          isLoading={branches.isLoading}
          error={branches.error}
          onRetry={branches.refetch}
          loadingHeight={160}
        >
          <DataTable<Branch>
            rows={branches.data ?? []}
            rowKey={(row) => row.id}
            emptyTitle="No branches"
            columns={[
              { key: 'name', header: 'Branch', render: (row) => row.name },
              { key: 'code', header: 'Code', render: (row) => row.code },
              {
                key: 'warehouses',
                header: 'Warehouses',
                numeric: true,
                render: (row) => row.warehouse_count,
              },
            ]}
          />
        </QueryState>
        {canManage ? (
          <CardBody>
            <FieldRow>
              <Input
                label="Branch name"
                value={branchForm.name}
                onChange={(event) =>
                  setBranchForm({ ...branchForm, name: event.target.value })
                }
              />
              <Input
                label="Code"
                value={branchForm.code}
                onChange={(event) =>
                  setBranchForm({ ...branchForm, code: event.target.value.toUpperCase() })
                }
              />
              <Button
                icon="plus"
                onClick={addBranch}
                isLoading={createBranch.isPending}
                disabled={!branchForm.name || !branchForm.code}
              >
                Add branch
              </Button>
            </FieldRow>
          </CardBody>
        ) : null}
      </Card>

      <Card>
        <CardHeader
          title="Warehouses"
          description="Shops sell from the counter; godowns hold bulk stock. Stock is tracked per warehouse."
        />
        <QueryState
          isLoading={warehouses.isLoading}
          error={warehouses.error}
          onRetry={warehouses.refetch}
          loadingHeight={160}
        >
          <DataTable<Warehouse>
            rows={warehouses.data ?? []}
            rowKey={(row) => row.id}
            emptyTitle="No warehouses"
            columns={[
              { key: 'name', header: 'Warehouse', render: (row) => row.name },
              { key: 'code', header: 'Code', render: (row) => row.code },
              {
                key: 'type',
                header: 'Type',
                render: (row) => (
                  <Badge tone={row.type === 'shop' ? 'brand' : 'neutral'}>
                    {row.type === 'shop' ? 'Shop' : 'Godown'}
                  </Badge>
                ),
              },
              {
                key: 'branch',
                header: 'Branch',
                secondary: true,
                render: (row) => row.branch_name ?? '—',
              },
            ]}
          />
        </QueryState>
        {canManage ? (
          <CardBody>
            <FieldRow>
              <Input
                label="Warehouse name"
                value={warehouseForm.name}
                onChange={(event) =>
                  setWarehouseForm({ ...warehouseForm, name: event.target.value })
                }
              />
              <Input
                label="Code"
                value={warehouseForm.code}
                onChange={(event) =>
                  setWarehouseForm({
                    ...warehouseForm,
                    code: event.target.value.toUpperCase(),
                  })
                }
              />
              <Select
                label="Type"
                value={warehouseForm.type}
                onChange={(event) =>
                  setWarehouseForm({
                    ...warehouseForm,
                    type: event.target.value as 'shop' | 'godown',
                  })
                }
              >
                <option value="shop">Shop</option>
                <option value="godown">Godown</option>
              </Select>
              <Select
                label="Branch"
                value={warehouseForm.branch_id}
                onChange={(event) =>
                  setWarehouseForm({ ...warehouseForm, branch_id: event.target.value })
                }
              >
                <option value="">No branch</option>
                {(branches.data ?? []).map((branch) => (
                  <option key={branch.id} value={branch.id}>
                    {branch.name}
                  </option>
                ))}
              </Select>
              <Button
                icon="plus"
                onClick={addWarehouse}
                isLoading={createWarehouse.isPending}
                disabled={!warehouseForm.name || !warehouseForm.code}
              >
                Add warehouse
              </Button>
            </FieldRow>
          </CardBody>
        ) : null}
      </Card>
    </div>
  );
}
