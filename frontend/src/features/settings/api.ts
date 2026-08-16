// Settings feature API: organization profile, branches, warehouses, users, roles.
import { apiFetch } from '@/lib/api/client';

export interface OrgProfile {
  id: string;
  name: string;
  legal_name: string | null;
  gstin: string | null;
  address: string | null;
  currency: string;
}

export interface Branch {
  id: string;
  name: string;
  code: string;
  address: string | null;
  is_active: boolean;
  warehouse_count: number;
}

export interface Warehouse {
  id: string;
  name: string;
  code: string;
  type: 'shop' | 'godown';
  branch_id: string | null;
  branch_name: string | null;
  is_active: boolean;
}

export interface OrgUser {
  id: string;
  email: string;
  full_name: string;
  is_owner: boolean;
  is_active: boolean;
  role_code: string | null;
  role_name: string | null;
  last_login_at: string | null;
}

export interface Role {
  id: string;
  code: string;
  name: string;
  description: string | null;
  is_system: boolean;
  permissions: string[];
  user_count: number;
}

export function fetchOrgProfile(): Promise<OrgProfile> {
  return apiFetch<OrgProfile>('/api/v1/org/profile');
}

export function updateOrgProfile(input: Partial<OrgProfile>): Promise<OrgProfile> {
  return apiFetch<OrgProfile>('/api/v1/org/profile', { method: 'PATCH', body: input });
}

export function fetchBranches(): Promise<Branch[]> {
  return apiFetch<Branch[]>('/api/v1/org/branches');
}

export function createBranch(input: {
  name: string;
  code: string;
  address?: string;
}): Promise<Branch> {
  return apiFetch<Branch>('/api/v1/org/branches', { method: 'POST', body: input });
}

export function fetchWarehouses(): Promise<Warehouse[]> {
  return apiFetch<Warehouse[]>('/api/v1/org/warehouses');
}

export function createWarehouse(input: {
  name: string;
  code: string;
  type: 'shop' | 'godown';
  branch_id?: string | null;
}): Promise<Warehouse> {
  return apiFetch<Warehouse>('/api/v1/org/warehouses', { method: 'POST', body: input });
}

export function fetchUsers(): Promise<OrgUser[]> {
  return apiFetch<OrgUser[]>('/api/v1/users');
}

export function fetchRoles(): Promise<Role[]> {
  return apiFetch<Role[]>('/api/v1/users/roles');
}

export interface CreateUserInput {
  email: string;
  password: string;
  full_name: string;
  role_code: string;
  branch_id?: string | null;
}

export function createUser(input: CreateUserInput): Promise<OrgUser> {
  return apiFetch<OrgUser>('/api/v1/users', { method: 'POST', body: input });
}

export interface UpdateUserInput {
  full_name?: string;
  is_active?: boolean;
  role_code?: string;
  password?: string;
}

export function updateUser(userId: string, input: UpdateUserInput): Promise<OrgUser> {
  return apiFetch<OrgUser>(`/api/v1/users/${userId}`, { method: 'PATCH', body: input });
}
