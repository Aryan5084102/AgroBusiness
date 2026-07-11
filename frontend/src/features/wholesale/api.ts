// Wholesale feature API: create order (with credit control) and dispatch→invoice.
import { apiFetch } from '@/lib/api/client';
import type { CartLine } from '@/features/pos/api';

export interface CreateOrderInput {
  warehouseId: string;
  customerId: string;
  lines: CartLine[];
  creditOverrideApproved?: boolean;
}

export interface OrderResult {
  sales_order_id: string;
  order_number: string;
  status: string;
  grand_total: string;
  warnings: string[];
}

export interface DispatchResult {
  sales_order_id: string;
  sales_invoice_id: string;
  invoice_number: string;
  grand_total: string;
}

export function createOrder(input: CreateOrderInput): Promise<OrderResult> {
  return apiFetch<OrderResult>('/api/v1/wholesale/orders', {
    method: 'POST',
    body: {
      warehouse_id: input.warehouseId,
      customer_id: input.customerId,
      lines: input.lines,
      is_quotation: false,
      credit_override_approved: input.creditOverrideApproved ?? false,
    },
  });
}

export function dispatchOrder(orderId: string): Promise<DispatchResult> {
  return apiFetch<DispatchResult>(`/api/v1/wholesale/orders/${orderId}/dispatch`, {
    method: 'POST',
  });
}
