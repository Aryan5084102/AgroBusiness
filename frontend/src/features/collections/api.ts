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
