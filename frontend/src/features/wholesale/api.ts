// Wholesale feature API: create an order/quotation with credit control.
import { apiFetch } from '@/lib/api/client';
import type { CartLine } from '@/features/pos/api';

export interface CreateOrderInput {
  warehouseId: string;
  customerId: string;
  lines: CartLine[];
  isQuotation?: boolean;
  creditOverrideApproved?: boolean;
}

export interface OrderResult {
  sales_order_id: string;
  order_number: string;
  status: string;
  grand_total: string;
  warnings: string[];
}

export function createOrder(input: CreateOrderInput): Promise<OrderResult> {
  return apiFetch<OrderResult>('/api/v1/wholesale/orders', {
    method: 'POST',
    body: {
      warehouse_id: input.warehouseId,
      customer_id: input.customerId,
      lines: input.lines,
      is_quotation: input.isQuotation ?? false,
      credit_override_approved: input.creditOverrideApproved ?? false,
    },
  });
}
