// Customers feature API.
import { apiFetch } from '@/lib/api/client';

export type CustomerType =
  'walk_in' | 'farmer' | 'retail' | 'retailer' | 'dealer' | 'distributor' | 'institution';

export interface Customer {
  id: string;
  code: string;
  name: string;
  customer_type: CustomerType;
  phone: string | null;
  gstin: string | null;
  village: string | null;
  credit_limit: string;
  credit_period_days: number;
  outstanding: string;
  available_credit: string;
  is_active: boolean;
}

export interface CreateCustomerInput {
  code: string;
  name: string;
  customer_type: CustomerType;
  phone?: string;
  gstin?: string;
  village?: string;
  credit_limit?: string;
  credit_period_days?: number;
}

export interface UpdateCustomerInput {
  name?: string;
  customer_type?: CustomerType;
  phone?: string;
  gstin?: string;
  village?: string;
  credit_limit?: string;
  credit_period_days?: number;
  is_active?: boolean;
}

export function fetchCustomers(search?: string): Promise<Customer[]> {
  const params = search ? `?search=${encodeURIComponent(search)}` : '';
  return apiFetch<Customer[]>(`/api/v1/customers${params}`);
}

export function fetchCustomer(customerId: string): Promise<Customer> {
  return apiFetch<Customer>(`/api/v1/customers/${customerId}`);
}

export function createCustomer(input: CreateCustomerInput): Promise<Customer> {
  return apiFetch<Customer>('/api/v1/customers', { method: 'POST', body: input });
}

export function updateCustomer(
  customerId: string,
  input: UpdateCustomerInput,
): Promise<Customer> {
  return apiFetch<Customer>(`/api/v1/customers/${customerId}`, {
    method: 'PATCH',
    body: input,
  });
}
