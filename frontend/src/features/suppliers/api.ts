// Suppliers feature API.
import { apiFetch } from '@/lib/api/client';

export interface Supplier {
  id: string;
  code: string;
  name: string;
  is_active: boolean;
}

export interface CreateSupplierInput {
  code: string;
  name: string;
  gstin?: string;
  phone?: string;
  credit_period_days?: number;
}

export function fetchSuppliers(): Promise<Supplier[]> {
  return apiFetch<Supplier[]>('/api/v1/suppliers');
}

export function createSupplier(input: CreateSupplierInput): Promise<Supplier> {
  return apiFetch<Supplier>('/api/v1/suppliers', { method: 'POST', body: input });
}
