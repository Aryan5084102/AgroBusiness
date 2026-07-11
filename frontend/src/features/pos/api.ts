// POS feature API: warehouses, cart quote, and invoice finalization.
import { apiFetch } from '@/lib/api/client';

export interface Warehouse {
  id: string;
  name: string;
  code: string;
  type: string;
  branch_id: string | null;
  is_active: boolean;
}

export interface CartLine {
  product_id: string;
  base_quantity: string;
  discount_percent?: string;
}

export interface QuoteLine {
  product_id: string;
  name: string;
  quantity: string;
  unit_price: string;
  price_source: string;
  net_amount: string;
  tax_amount: string;
  line_total: string;
  available_stock: string;
}

export interface Quote {
  lines: QuoteLine[];
  subtotal: string;
  tax_total: string;
  grand_total: string;
  warnings: string[];
}

export interface FinalizeResult {
  invoice_id: string;
  invoice_number: string;
  grand_total: string;
  paid_amount: string;
  payment_status: string;
  replayed: boolean;
  warnings: string[];
}

export type PaymentMethod = 'cash' | 'upi' | 'card';

export function fetchWarehouses(): Promise<Warehouse[]> {
  return apiFetch<Warehouse[]>('/api/v1/org/warehouses');
}

export function fetchQuote(warehouseId: string, lines: CartLine[]): Promise<Quote> {
  return apiFetch<Quote>('/api/v1/pos/quote', {
    method: 'POST',
    body: { warehouse_id: warehouseId, lines },
  });
}

export interface FinalizeInput {
  warehouseId: string;
  customerId?: string | null;
  lines: CartLine[];
  method: PaymentMethod;
  amount: string;
  idempotencyKey: string;
}

export function finalizeSale(input: FinalizeInput): Promise<FinalizeResult> {
  return apiFetch<FinalizeResult>('/api/v1/pos/invoices', {
    method: 'POST',
    headers: { 'Idempotency-Key': input.idempotencyKey },
    body: {
      warehouse_id: input.warehouseId,
      customer_id: input.customerId ?? null,
      lines: input.lines,
      payments: [{ method: input.method, amount: input.amount }],
    },
  });
}
