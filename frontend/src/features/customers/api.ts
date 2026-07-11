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
  credit_limit: string;
  outstanding: string;
  available_credit: string;
  is_active: boolean;
}

export interface CreateCustomerInput {
  code: string;
  name: string;
  customer_type: CustomerType;
  phone?: string;
  credit_limit?: string;
}

export function fetchCustomers(search?: string): Promise<Customer[]> {
  const params = search ? `?search=${encodeURIComponent(search)}` : '';
  return apiFetch<Customer[]>(`/api/v1/customers${params}`);
}

export function createCustomer(input: CreateCustomerInput): Promise<Customer> {
  return apiFetch<Customer>('/api/v1/customers', { method: 'POST', body: input });
}
