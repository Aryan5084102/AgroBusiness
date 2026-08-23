// Reporting API: registers, valuation, trend, top products, CSV export.
import { apiFetch } from '@/lib/api/client';

export interface RegisterRow {
  entry_date: string;
  document_number: string;
  party: string;
  category: string;
  taxable_value: string;
  tax_amount: string;
  total: string;
  settled: string;
  status: string;
}

export interface RegisterResponse {
  rows: RegisterRow[];
  total_taxable: string;
  total_tax: string;
  grand_total: string;
}

export interface GstBucket {
  gst_rate: string;
  taxable_value: string;
  tax_amount: string;
}

export interface GstSummary {
  buckets: GstBucket[];
  total_taxable: string;
  total_tax: string;
}

export interface StockValuationRow {
  product_id: string;
  product_name: string;
  sku: string;
  on_hand: string;
  min_stock: string;
  retail_price: string;
  stock_value: string;
  is_low: boolean;
}

export interface StockValuation {
  rows: StockValuationRow[];
  total_value: string;
  low_stock_count: number;
}

export interface TopProduct {
  product_id: string;
  product_name: string;
  sku: string;
  quantity_sold: string;
  revenue: string;
}

export interface TrendPoint {
  day: string;
  revenue: string;
  invoice_count: number;
}

export type RegisterKind = 'sales' | 'purchases';

export function fetchSalesRegister(from: string, to: string): Promise<RegisterResponse> {
  return apiFetch<RegisterResponse>(
    `/api/v1/reports/sales-register?date_from=${from}&date_to=${to}`,
  );
}

export function fetchPurchaseRegister(
  from: string,
  to: string,
): Promise<RegisterResponse> {
  return apiFetch<RegisterResponse>(
    `/api/v1/reports/purchase-register?date_from=${from}&date_to=${to}`,
  );
}

export function fetchGstSummary(from: string, to: string): Promise<GstSummary> {
  return apiFetch<GstSummary>(
    `/api/v1/reports/gst-summary?date_from=${from}&date_to=${to}`,
  );
}

export function fetchStockValuation(): Promise<StockValuation> {
  return apiFetch<StockValuation>('/api/v1/reports/stock-valuation');
}

export function fetchTopProducts(days = 30, limit = 8): Promise<TopProduct[]> {
  return apiFetch<TopProduct[]>(
    `/api/v1/reports/top-products?days=${days}&limit=${limit}`,
  );
}

export function fetchSalesTrend(days = 14): Promise<TrendPoint[]> {
  return apiFetch<TrendPoint[]>(`/api/v1/reports/sales-trend?days=${days}`);
}

/**
 * Streams a register as CSV. The endpoint sets a Content-Disposition filename,
 * so this fetches the blob and hands it to the browser's download flow (a plain
 * link would not carry the session cookie in every browser configuration).
 */
export async function downloadRegisterCsv(
  register: RegisterKind,
  from: string,
  to: string,
): Promise<void> {
  const response = await fetch(
    `/api/v1/reports/export/${register}?date_from=${from}&date_to=${to}`,
    { credentials: 'include' },
  );
  if (!response.ok) {
    throw new Error('The export could not be generated.');
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${register}-register-${from}-to-${to}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
