// Collections feature API: outstanding invoices + receive payment.
import { apiFetch } from '@/lib/api/client';
import type { PaymentMethod } from '@/features/pos/api';

export interface OutstandingInvoice {
  id: string;
  invoice_number: string;
  invoice_date: string;
  grand_total: string;
  paid_amount: string;
  outstanding: string;
  payment_status: string;
}

export interface Outstanding {
  invoices: OutstandingInvoice[];
  total_outstanding: string;
}

export interface PaymentResult {
  payment_id: string;
  allocated_total: string;
  unallocated: string;
  settled_invoice_ids: string[];
}

export function fetchOutstanding(customerId: string): Promise<Outstanding> {
  return apiFetch<Outstanding>(
    `/api/v1/collections/outstanding?customer_id=${encodeURIComponent(customerId)}`,
  );
}

export interface ReceivePaymentInput {
  customerId: string;
  amount: string;
  method: PaymentMethod;
  reference?: string;
}

export function receivePayment(input: ReceivePaymentInput): Promise<PaymentResult> {
  return apiFetch<PaymentResult>('/api/v1/collections/payments', {
    method: 'POST',
    body: {
      customer_id: input.customerId,
      amount: input.amount,
      method: input.method,
      reference: input.reference,
    },
  });
}

// --- Receivables & payment history -----------------------------------------
export interface ReceivableRow {
  customer_id: string;
  customer_name: string;
  customer_code: string;
  phone: string | null;
  open_invoices: number;
  outstanding: string;
  oldest_invoice_date: string | null;
  days_overdue: number;
}

export interface Receivables {
  rows: ReceivableRow[];
  total_outstanding: string;
}

export interface PaymentRecord {
  id: string;
  received_at: string;
  customer_id: string | null;
  customer_name: string | null;
  method: PaymentMethod | 'bank_transfer' | 'cheque' | 'credit' | 'advance';
  amount: string;
  reference: string | null;
  received_by: string | null;
}

export interface PaymentHistory {
  items: PaymentRecord[];
  total: number;
  limit: number;
  offset: number;
  total_amount: string;
}

export function fetchReceivables(): Promise<Receivables> {
  return apiFetch<Receivables>('/api/v1/collections/receivables');
}

export function fetchPayments(params: {
  customerId?: string;
  limit?: number;
  offset?: number;
}): Promise<PaymentHistory> {
  const search = new URLSearchParams();
  if (params.customerId) search.set('customer_id', params.customerId);
  search.set('limit', String(params.limit ?? 25));
  search.set('offset', String(params.offset ?? 0));
  return apiFetch<PaymentHistory>(`/api/v1/collections/payments?${search.toString()}`);
}
