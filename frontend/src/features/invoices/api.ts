// Invoice & order history API (retail invoices, wholesale orders, goods receipts).
import { apiFetch } from '@/lib/api/client';

export type PaymentStatus = 'paid' | 'partial' | 'credit';
export type SaleChannel = 'retail' | 'wholesale';

export interface InvoiceListItem {
  id: string;
  invoice_number: string;
  invoice_date: string;
  channel: SaleChannel;
  customer_name: string | null;
  warehouse_name: string;
  grand_total: string;
  paid_amount: string;
  outstanding: string;
  payment_status: PaymentStatus;
  created_by_name: string | null;
}

export interface InvoiceItem {
  product_id: string;
  product_name: string;
  sku: string;
  hsn_code: string | null;
  unit_code: string;
  base_quantity: string;
  unit_price: string;
  price_source: string;
  discount_amount: string;
  taxable_value: string;
  gst_rate: string;
  tax_amount: string;
  line_total: string;
}

export interface InvoicePayment {
  method: 'cash' | 'upi' | 'card' | 'cheque' | 'bank_transfer' | 'credit';
  amount: string;
  reference: string | null;
}

export interface InvoiceDetail extends InvoiceListItem {
  subtotal: string;
  discount_total: string;
  tax_total: string;
  customer_id: string | null;
  customer_phone: string | null;
  customer_gstin: string | null;
  customer_address: string | null;
  customer_village: string | null;
  items: InvoiceItem[];
  payments: InvoicePayment[];
}

export interface InvoicePage {
  items: InvoiceListItem[];
  total: number;
  limit: number;
  offset: number;
  total_value: string;
}

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, String(value));
  }
  const encoded = search.toString();
  return encoded ? `?${encoded}` : '';
}

export interface InvoiceQuery {
  channel?: SaleChannel;
  customerId?: string;
  paymentStatus?: PaymentStatus;
  search?: string;
  limit?: number;
  offset?: number;
}

export function fetchInvoices(params: InvoiceQuery): Promise<InvoicePage> {
  return apiFetch<InvoicePage>(
    `/api/v1/pos/invoices${query({
      channel: params.channel,
      customer_id: params.customerId,
      payment_status: params.paymentStatus,
      search: params.search,
      limit: params.limit ?? 25,
      offset: params.offset ?? 0,
    })}`,
  );
}

export function fetchInvoice(invoiceId: string): Promise<InvoiceDetail> {
  return apiFetch<InvoiceDetail>(`/api/v1/pos/invoices/${invoiceId}`);
}

// --- Wholesale orders -------------------------------------------------------
export type OrderStatus =
  | 'quotation'
  | 'confirmed'
  | 'partially_dispatched'
  | 'dispatched'
  | 'invoiced'
  | 'cancelled';

export interface OrderListItem {
  id: string;
  order_number: string;
  order_date: string;
  status: OrderStatus;
  customer_id: string;
  customer_name: string;
  warehouse_name: string;
  grand_total: string;
  credit_override_approved: boolean;
  sales_invoice_id: string | null;
}

export interface OrderItem {
  product_id: string;
  product_name: string;
  sku: string;
  base_quantity: string;
  reserved_quantity: string;
  dispatched_quantity: string;
  unit_price: string;
  price_source: string;
  taxable_value: string;
  gst_rate: string;
  tax_amount: string;
  line_total: string;
}

export interface OrderDetail extends OrderListItem {
  subtotal: string;
  tax_total: string;
  items: OrderItem[];
}

export interface OrderPage {
  items: OrderListItem[];
  total: number;
  limit: number;
  offset: number;
  open_value: string;
}

export function fetchOrders(params: {
  status?: OrderStatus;
  search?: string;
  limit?: number;
  offset?: number;
}): Promise<OrderPage> {
  return apiFetch<OrderPage>(
    `/api/v1/wholesale/orders${query({
      status: params.status,
      search: params.search,
      limit: params.limit ?? 25,
      offset: params.offset ?? 0,
    })}`,
  );
}

export function fetchOrder(orderId: string): Promise<OrderDetail> {
  return apiFetch<OrderDetail>(`/api/v1/wholesale/orders/${orderId}`);
}

export function dispatchOrder(orderId: string): Promise<{
  sales_order_id: string;
  sales_invoice_id: string;
  invoice_number: string;
  grand_total: string;
}> {
  return apiFetch(`/api/v1/wholesale/orders/${orderId}/dispatch`, { method: 'POST' });
}

// --- Goods receipts ---------------------------------------------------------
export interface ReceiptListItem {
  id: string;
  grn_number: string;
  receipt_date: string;
  supplier_id: string;
  supplier_name: string;
  warehouse_name: string;
  line_count: number;
  total_value: string;
}

export interface ReceiptItem {
  product_id: string;
  product_name: string;
  sku: string;
  received_base_quantity: string;
  free_base_quantity: string;
  unit_rate: string;
  landed_unit_cost: string;
  line_value: string;
}

export interface ReceiptDetail extends ReceiptListItem {
  items: ReceiptItem[];
}

export interface ReceiptPage {
  items: ReceiptListItem[];
  total: number;
  limit: number;
  offset: number;
}

export function fetchReceipts(params: {
  search?: string;
  limit?: number;
  offset?: number;
}): Promise<ReceiptPage> {
  return apiFetch<ReceiptPage>(
    `/api/v1/purchases/goods-receipts${query({
      search: params.search,
      limit: params.limit ?? 25,
      offset: params.offset ?? 0,
    })}`,
  );
}

export function fetchReceipt(receiptId: string): Promise<ReceiptDetail> {
  return apiFetch<ReceiptDetail>(`/api/v1/purchases/goods-receipts/${receiptId}`);
}
